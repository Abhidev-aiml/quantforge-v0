from engine.loader import load_strategy, validate_signals, StrategyError
from engine.data import load_csv

df = load_csv("data/raw/xauusd_1h_comma.csv")   # or a real CSV

# Experiment 1: happy path
fn = load_strategy("strategies/buy_hold.py")
sig = validate_signals(fn(df), df)
print("Exp 1 ✅ buy_hold:", sig.iloc[0], sig.iloc[-1], sig.dtype)

# Experiment 2: SMA strategy
fn = load_strategy("strategies/sma_cross.py")
sig = validate_signals(fn(df), df)
print("Exp 2 ✅ sma_cross: unique values:", sig.unique())

# Experiment 3: wrong return type
try:
    fn = load_strategy("strategies/broken_wrong_type.py")
    validate_signals(fn(df), df)
except StrategyError as e:
    print("Exp 3 ✅ caught:", e)

# Experiment 4: no generate_signals function
try:
    load_strategy("strategies/broken_no_function.py")
except StrategyError as e:
    print("Exp 4 ✅ caught:", e)

# Experiment 5: leverage out of range
try:
    fn = load_strategy("strategies/broken_leverage.py")
    validate_signals(fn(df), df)
except StrategyError as e:
    print("Exp 5 ✅ caught:", e)