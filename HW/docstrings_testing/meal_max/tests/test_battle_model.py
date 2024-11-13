import pytest
from meal_max.models.battle_model import BattleModel
from meal_max.models.kitchen_model import Meal

@pytest.fixture
def battle_model():
    """Create a new BattleModel instance for each test."""
    return BattleModel()

@pytest.fixture
def sample_meal1():
    """Provide a sample meal instance. (Making foods fight is way funnier. Id watch that.)"""
    return Meal(id=1, meal="Pasta", cuisine="Italian", price=15.0, difficulty="MED")

@pytest.fixture
def sample_meal2():
    """Provide another sample meal instance."""
    return Meal(id=2, meal="Sushi", cuisine="Japanese", price=20.0, difficulty="HIGH")

def test_initialization(battle_model):
    """Test that a new BattleModel initializes with an empty list of combatants."""
    assert battle_model.combatants == []

def test_prep_combatant(battle_model, sample_meal1):
    """Test adding a combatant to the list."""
    battle_model.prep_combatant(sample_meal1)
    assert len(battle_model.combatants) == 1
    assert battle_model.combatants[0] == sample_meal1

def test_prep_combatant_full(battle_model, sample_meal1, sample_meal2):
    """Test that adding more than two combatants raises an error."""
    battle_model.prep_combatant(sample_meal1)
    battle_model.prep_combatant(sample_meal2)
    with pytest.raises(ValueError, match="Combatant list is full"):
        battle_model.prep_combatant(sample_meal1)

def test_clear_combatants(battle_model, sample_meal1, sample_meal2):
    """Test clearing all combatants from the list."""
    battle_model.prep_combatant(sample_meal1)
    battle_model.prep_combatant(sample_meal2)
    battle_model.clear_combatants()
    assert len(battle_model.combatants) == 0

def test_get_combatants(battle_model, sample_meal1):
    """Test retrieving the current list of combatants."""
    battle_model.prep_combatant(sample_meal1)
    combatants = battle_model.get_combatants()
    assert len(combatants) == 1
    assert combatants[0] == sample_meal1

def test_get_battle_score(battle_model, sample_meal1):
    """Test calculating a battle score for a combatant."""
    score = battle_model.get_battle_score(sample_meal1)
    expected_score = (sample_meal1.price * len(sample_meal1.cuisine)) - 2 
    assert score == expected_score

def test_battle_insufficient_combatants(battle_model):
    """Test that a battle cannot start with fewer than two combatants."""
    with pytest.raises(ValueError, match="Two combatants prepped"):
        battle_model.battle()

def test_battle_success(battle_model, sample_meal1, sample_meal2):
    """Test a successful battle between two combatants."""
    battle_model.prep_combatant(sample_meal1)
    battle_model.prep_combatant(sample_meal2)

    winner = battle_model.battle()
    assert winner in [sample_meal1.meal, sample_meal2.meal]
    assert len(battle_model.combatants) == 1
    assert battle_model.combatants[0].meal == winner

