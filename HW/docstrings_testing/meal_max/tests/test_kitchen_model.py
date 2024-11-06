from contextlib import contextmanager
import re
import sqlite3

import pytest

from meal_max.models.kitchen_model import (
    Meal,
    create_meal,
    clear_meals,
    delete_meal,
    get_leaderboard,
    get_meal_by_id, 
    get_meal_by_name,
    update_meal_stats
)

######################################################
#
#    Fixtures
#
######################################################

def normalize_whitespace(sql_query: str) -> str:
    return re.sub(r'\s+', ' ', sql_query).strip()

# Mocking the database connection for tests
@pytest.fixture
def mock_cursor(mocker):
    mock_conn = mocker.Mock()
    mock_cursor = mocker.Mock()

    # Mock the connection's cursor
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = None  # Default return for queries
    mock_cursor.fetchall.return_value = []
    mock_conn.commit.return_value = None

    # Mock the get_db_connection context manager from sql_utils
    @contextmanager
    def mock_get_db_connection():
        yield mock_conn  # Yield the mocked connection object

    mocker.patch("meal_max.models.kitchen_model.get_db_connection", mock_get_db_connection)

    return mock_cursor  # Return the mock cursor so we can set expectations per test

######################################################
#
#    create_meal
#
######################################################

def test_create_meal(mock_cursor):

    """Test creating a new meal."""

    # Call the function to create a new meal
    create_meal(meal="fried chicken", cuisine="korean", price=5.0, difficulty="LOW")

    expected_query = normalize_whitespace("""
        INSERT INTO meals (meal, cuisine, price, difficulty)
        VALUES (?, ?, ?, ?)
    """)

    actual_query = normalize_whitespace(mock_cursor.execute.call_args[0][0])

    # Assert that the SQL query was correct
    assert actual_query == expected_query, "The SQL query did not match the expected structure."

    # Extract the arguments used in the SQL call (second element of call_args)
    actual_arguments = mock_cursor.execute.call_args[0][1]

    # Assert that the SQL query was executed with the correct arguments
    expected_arguments = ("fried chicken", "korean", 5.0, "LOW")
    assert actual_arguments == expected_arguments, f"The SQL query arguments did not match. Expected {expected_arguments}, got {actual_arguments}."

def test_create_meal_duplicate(mock_cursor):

    """Test creating a meal with a duplicate name, cuisine, price, and difficulty (should raise an error)."""

    # Simulate that the database will raise an IntegrityError due to a duplicate entry
    mock_cursor.execute.side_effect = sqlite3.IntegrityError("UNIQUE constraint failed: meals.name, meals.cuisine, meal.price, meal.difficulty")

    # Expect the function to raise a ValueError with a specific message when handling the IntegrityError
    with pytest.raises(ValueError, match="Meal with name 'fried chicken' already exists"):
        create_meal(meal="fried chicken", cuisine="korean", price=5.0, difficulty="LOW")

def test_create_meal_invalid_price(mock_cursor): 

    """Test creating a meal with a negative price"""

    with pytest.raises(ValueError, match="Invalid price: -9. Price must be a positive number."):
        create_meal(meal="pasta", cuisine="italian", price=-9, difficulty="LOW")
    
    """Test creating a meal with a non-integer price"""

    with pytest.raises(ValueError, match="Invalid price: price. Price must be a positive number"):
        create_meal(meal="pasta", cuisine="italian", price="price", difficulty="LOW")

def test_create_meal_invalid_difficulty(mock_cursor):

    """Test creating a meal with an invalid difficulty"""

    with pytest.raises(ValueError, match="Invalid difficulty level: DIFFICULT. Must be 'LOW', 'MED', or 'HIGH'."):
        create_meal(meal="pasta", cuisine="italian", price=5.0, difficulty="DIFFICULT")

######################################################
#
#    clear_meal & delete_meal
#
######################################################

def test_clear_meals(mock_cursor, mocker):

    """Test clearing all meals from the catalog (removes all meals)."""

    # Mock the file reading
    mocker.patch.dict('os.environ', {'SQL_CREATE_TABLE_PATH': 'sql/create_meal_table.sql'})
    mock_open = mocker.patch('builtins.open', mocker.mock_open(read_data="The body of the create statement"))

    # Call the clear_database function
    clear_meals()

    # Ensure the file was opened using the environment variable's path
    mock_open.assert_called_once_with('sql/create_meal_table.sql', 'r')

    # Verify that the correct SQL script was executed
    mock_cursor.executescript.assert_called_once()
 
def test_delete_meal(mock_cursor):

    """Test deleting a meal from the catalog"""

    # Simulate that the song exists (id = 1)
    mock_cursor.fetchone.return_value = ([False])

    # Call the delete_song function
    delete_meal(1)

    # Normalize the SQL for both queries (SELECT and UPDATE)
    expected_select_sql = normalize_whitespace("SELECT deleted FROM meals WHERE id = ?")
    expected_update_sql = normalize_whitespace("UPDATE meals SET deleted = TRUE WHERE id = ?")

    # Access both calls to `execute()` using `call_args_list`
    actual_select_sql = normalize_whitespace(mock_cursor.execute.call_args_list[0][0][0])
    actual_update_sql = normalize_whitespace(mock_cursor.execute.call_args_list[1][0][0])

    # Ensure the correct SQL queries were executed
    assert actual_select_sql == expected_select_sql, "The SELECT query did not match the expected structure."
    assert actual_update_sql == expected_update_sql, "The UPDATE query did not match the expected structure."

    # Ensure the correct arguments were used in both SQL queries
    expected_select_args = (1,)
    expected_update_args = (1,)

    actual_select_args = mock_cursor.execute.call_args_list[0][0][1]
    actual_update_args = mock_cursor.execute.call_args_list[1][0][1]

    assert actual_select_args == expected_select_args, f"The SELECT query arguments did not match. Expected {expected_select_args}, got {actual_select_args}."
    assert actual_update_args == expected_update_args, f"The UPDATE query arguments did not match. Expected {expected_update_args}, got {actual_update_args}."

def test_delete_meal_already_deleted(mock_cursor):

    """Test deleting a meal that has already been deleted"""

    with pytest.raises(ValueError, match="Meal with ID 1 has been deleted"):
        mock_cursor.fetchone.return_value = ([True])
        delete_meal(1)

def test_delete_meal_doesnt_exist(mock_cursor):

    """Test deleting a meal that doesn't exist"""

    with pytest.raises(ValueError, match="Meal with ID 2 not found"):
        mock_cursor.fetchone.return_value = None
        delete_meal(2)

######################################################
#
#    get_leaderboard 
#
######################################################

def test_get_leaderboard_by_wins(mock_cursor):
    
    """Test getting leaderboard by sorting by wins"""

    # Simulate that there are multiple songs in the database
    mock_cursor.fetchall.return_value = [
        (3, "curry", "indian", 4.0, "HIGH", 10, 8, (8 * 1.0 / 10)),
        (2, "pasta", "italian", 2.0, "LOW", 10, 6, (6 * 1.0 / 10)),
        (1, "fried chicken", "korean", 5.0, "MED", 10, 2, (2 * 1.0 / 10))
    ]

    # Call the get_all_songs function
    leaderboard = get_leaderboard(sort_by="wins")

    # Ensure the results match the expected output
    expected_result = [
        {"id": 3, "meal": "curry", "cuisine": "indian", "price": 4.0, "difficulty": "HIGH", "battles": 10, "wins": 8, "win_pct": 80.0},
        {"id": 2, "meal": "pasta", "cuisine": "italian", "price": 2.0, "difficulty": "LOW", "battles": 10, "wins": 6, "win_pct": 60.0},
        {"id": 1, "meal": "fried chicken", "cuisine": "korean", "price": 5.0, "difficulty": "MED", "battles": 10, "wins": 2, "win_pct": 20.0}
    ]

    assert leaderboard == expected_result, f"Expected {expected_result}, but got {leaderboard}"

def test_get_leaderboard_by_win_pct(mock_cursor):
    
    """Test getting leaderboard by sorting by wins_pct"""

    # Simulate that there are multiple songs in the database
    mock_cursor.fetchall.return_value = [
        (3, "curry", "indian", 4.0, "HIGH", 10, 8, (8 * 1.0 / 10)),
        (2, "pasta", "italian", 2.0, "LOW", 10, 6, (6 * 1.0 / 10)),
        (1, "fried chicken", "korean", 5.0, "MED", 10, 2, (2 * 1.0 / 10))
    ]

    # Call the get_all_songs function
    leaderboard = get_leaderboard(sort_by="win_pct")

    # Ensure the results match the expected output
    expected_result = [
        {"id": 3, "meal": "curry", "cuisine": "indian", "price": 4.0, "difficulty": "HIGH", "battles": 10, "wins": 8, "win_pct": 80.0},
        {"id": 2, "meal": "pasta", "cuisine": "italian", "price": 2.0, "difficulty": "LOW", "battles": 10, "wins": 6, "win_pct": 60.0},
        {"id": 1, "meal": "fried chicken", "cuisine": "korean", "price": 5.0, "difficulty": "MED", "battles": 10, "wins": 2, "win_pct": 20.0}
    ]

    assert leaderboard == expected_result, f"Expected {expected_result}, but got {leaderboard}"

def test_get_leaderboard_empty(mock_cursor):

    """test getting leaderboard on an empty leaderboard"""

    mock_cursor.fetchall.return_value = []

    # Call the get_all_songs function
    leaderboard = get_leaderboard()

    # Ensure the results match the expected output
    expected_result = []

    assert leaderboard == expected_result, f"Expected {expected_result}, but got {leaderboard}"

def test_get_leaderboard_invalid_sort():

    """Test getting leaderboard with an invalid sort_by parameter."""

    with pytest.raises(ValueError, match="Invalid sort_by parameter: invalid_sort"):
        get_leaderboard(sort_by="invalid_sort")

######################################################
#
#    get_meal_by_id
#
######################################################

def test_get_meal_by_id(mock_cursor):

    """Test getting a meal by id"""

    # Simulate that the song exists (id = 1)
    mock_cursor.fetchone.return_value = (1, "pasta", "italian", 3.0, "LOW", False)

    # Call the function and check the result
    result = get_meal_by_id(1)

    # Expected result based on the simulated fetchone return value
    expected_result = Meal(1, "pasta", "italian", 3.0, "LOW")

    # Ensure the result matches the expected output
    assert result == expected_result, f"Expected {expected_result}, got {result}"

    # Ensure the SQL query was executed correctly
    expected_query = normalize_whitespace("SELECT id, meal, cuisine, price, difficulty, deleted FROM meals WHERE id = ?")
    actual_query = normalize_whitespace(mock_cursor.execute.call_args[0][0])

    # Assert that the SQL query was correct
    assert actual_query == expected_query, "The SQL query did not match the expected structure."

    # Extract the arguments used in the SQL call
    actual_arguments = mock_cursor.execute.call_args[0][1]

    # Assert that the SQL query was executed with the correct arguments
    expected_arguments = (1,)
    assert actual_arguments == expected_arguments, f"The SQL query arguments did not match. Expected {expected_arguments}, got {actual_arguments}."

def test_get_meal_by_id_already_deleted(mock_cursor):

    """Test getting a meal with id using an invalid id"""

    with pytest.raises(ValueError, match="Meal with ID 1 has been deleted"):
        mock_cursor.fetchone.return_value = (1, "pasta", "italian", 3.0, "LOW", True)
        get_meal_by_id(1)

def test_get_meal_by_id_doesnt_exist(mock_cursor):

    """Test getting a meal with an id that doesn't exist"""

    with pytest.raises(ValueError, match="Meal with ID 1 not found"):
        mock_cursor.fetchone.return_value = None 
        get_meal_by_id(1)

######################################################
#
#    get_meal_by_name 
#
######################################################

def test_get_meal_by_name(mock_cursor):

    """Test getting a meal with name"""

    # Simulate that the song exists (id = 1)
    mock_cursor.fetchone.return_value = (1, "pasta", "italian", 3.0, "LOW", False)

    # Call the function and check the result
    result = get_meal_by_name("pasta")

    # Expected result based on the simulated fetchone return value
    expected_result = Meal(1, "pasta", "italian", 3.0, "LOW")

    # Ensure the result matches the expected output
    assert result == expected_result, f"Expected {expected_result}, got {result}"

    # Ensure the SQL query was executed correctly
    expected_query = normalize_whitespace("SELECT id, meal, cuisine, price, difficulty, deleted FROM meals WHERE meal = ?")
    actual_query = normalize_whitespace(mock_cursor.execute.call_args[0][0])

    # Assert that the SQL query was correct
    assert actual_query == expected_query, "The SQL query did not match the expected structure."

    # Extract the arguments used in the SQL call
    actual_arguments = mock_cursor.execute.call_args[0][1]

    # Assert that the SQL query was executed with the correct arguments
    expected_arguments = ("pasta",)
    assert actual_arguments == expected_arguments, f"The SQL query arguments did not match. Expected {expected_arguments}, got {actual_arguments}."

def test_get_meal_by_name_deleted(mock_cursor):

    """Tests getting a meal with name but its already been deleted"""

    with pytest.raises(ValueError, match="Meal with name pasta has been deleted"):
        mock_cursor.fetchone.return_value = (1, "pasta", "italian", 3.0, "LOW", True)
        get_meal_by_name("pasta")

def test_get_meal_by_name_doesnt_exist(mock_cursor):

    """Tests getting a meal with name but it doesn't exist"""

    with pytest.raises(ValueError, match="Meal with name pasta not found"):
        mock_cursor.fetchone.return_value = None
        get_meal_by_name("pasta")

######################################################
#
#    update_meal_stats 
#
######################################################
def test_update_meal_stats_win(mock_cursor):

    """Test updating a meal's win"""

    # Simulate that the song exists and is not deleted (id = 1)
    mock_cursor.fetchone.return_value = [False]

    # Call the update_play_count function with a sample song ID
    meal_id = 1
    update_meal_stats(meal_id, "win")

    # Normalize the expected SQL query
    expected_query = normalize_whitespace("""
        UPDATE meals SET battles = battles + 1, wins = wins + 1 WHERE id = ?
    """)

    # Ensure the SQL query was executed correctly
    actual_query = normalize_whitespace(mock_cursor.execute.call_args_list[1][0][0])

    # Assert that the SQL query was correct
    assert actual_query == expected_query, "The SQL query did not match the expected structure."

    # Extract the arguments used in the SQL call
    actual_arguments = mock_cursor.execute.call_args_list[1][0][1]

    # Assert that the SQL query was executed with the correct arguments (song ID)
    expected_arguments = (meal_id,)
    assert actual_arguments == expected_arguments, f"The SQL query arguments did not match. Expected {expected_arguments}, got {actual_arguments}."

def test_update_meal_stats_loss(mock_cursor):

    """Test updating a meal's loss"""

    # Simulate that the song exists and is not deleted (id = 1)
    mock_cursor.fetchone.return_value = [False]

    # Call the update_play_count function with a sample song ID
    meal_id = 1
    update_meal_stats(meal_id, "loss")

    # Normalize the expected SQL query
    expected_query = normalize_whitespace("""
        UPDATE meals SET battles = battles + 1 WHERE id = ?
    """)

    # Ensure the SQL query was executed correctly
    actual_query = normalize_whitespace(mock_cursor.execute.call_args_list[1][0][0])

    # Assert that the SQL query was correct
    assert actual_query == expected_query, "The SQL query did not match the expected structure."

    # Extract the arguments used in the SQL call
    actual_arguments = mock_cursor.execute.call_args_list[1][0][1]

    # Assert that the SQL query was executed with the correct arguments (song ID)
    expected_arguments = (meal_id,)
    assert actual_arguments == expected_arguments, f"The SQL query arguments did not match. Expected {expected_arguments}, got {actual_arguments}."

def test_update_meal_stats_deleted_id(mock_cursor):

    """Test updating meal stats with an id that has already been deleted"""

    with pytest.raises(ValueError, match="Meal with ID 1 has been deleted"):
        mock_cursor.fetchone.return_value = [True]
        meal_id = 1
        update_meal_stats(meal_id, "loss")

def test_update_meal_stats_id_not_found(mock_cursor):

    """Test upating meal stats with an id that is not found"""

    with pytest.raises(ValueError, match="Meal with ID 1 not found"):
        mock_cursor.fetchone.return_value = None 
        meal_id = 1
        update_meal_stats(meal_id, "loss") 

def test_update_meal_stats_with_invalid_stats(mock_cursor):

    """Test updating meal stats with an invalid stat"""

    with pytest.raises(ValueError, match="Invalid result: result. Expected 'win' or 'loss'."):
        mock_cursor.fetchone.return_value = [False]
        meal_id = 1 
        update_meal_stats(meal_id, "result")