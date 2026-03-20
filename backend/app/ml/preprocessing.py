import pandas as pd
import numpy as np
from typing import Optional
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import logging

# Optional: imblearn may not be installed on all environments
try:
    from imblearn.over_sampling import SMOTE
    IMBLEARN_AVAILABLE = True
except ImportError:
    IMBLEARN_AVAILABLE = False
    SMOTE = None

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# individual pipeline steps

def load_dataset(path: str) -> pd.DataFrame:
    """Read csv file into a DataFrame."""
    logging.info("Loading dataset...")
    return pd.read_csv(path)

def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """Perform basic cleaning such as handling missing values."""
    logging.info("Cleaning data...")
    df = df.copy()
    if df.isnull().values.any():
        for col in df.columns:
            if df[col].dtype in ["float64", "int64"]:
                df[col] = df[col].fillna(df[col].median())
            else:
                df[col] = df[col].fillna(df[col].mode().iloc[0])
    return df

def feature_engineering(df: pd.DataFrame) -> pd.DataFrame:
    """Add engineered features to the dataset."""
    logging.info("Performing feature engineering...")
    df = df.copy()
    if "Time" in df.columns:
        df["hour_of_day"] = (df["Time"] // 3600) % 24
    return df

def scale_features(df: pd.DataFrame, scaler: Optional[StandardScaler] = None) -> (pd.DataFrame, StandardScaler):
    """Scale numeric columns using StandardScaler."""
    logging.info("Scaling features...")
    df = df.copy()
    if scaler is None:
        scaler = StandardScaler()
    numeric_columns = df.select_dtypes(include=["float64", "int64"]).columns
    df[numeric_columns] = scaler.fit_transform(df[numeric_columns])
    return df, scaler

def handle_class_imbalance(X: pd.DataFrame, y: pd.Series) -> (pd.DataFrame, pd.Series):
    """Apply SMOTE to balance the classes if imblearn is available."""
    if not IMBLEARN_AVAILABLE:
        logging.warning("imblearn not installed — skipping SMOTE resampling")
        return X, y.astype(int)

    logging.info("Handling class imbalance...")
    sm = SMOTE(random_state=42)

    # Ensure y is integer labels
    y = y.astype(int)

    X_res, y_res = sm.fit_resample(X, y)

    return X_res, y_res

def split_data(X: pd.DataFrame, y: pd.Series, test_size: float = 0.2, random_state: int = 42):
    """Split features and target into train/test sets."""
    logging.info("Splitting data into train and test sets...")
    return train_test_split(X, y, test_size=test_size, random_state=random_state)

def prepare_training_data(
    path: str,
    target_column: str = "Class",
    test_size: float = 0.2,
    random_state: int = 42,
):
    """Execute full preprocessing pipeline and return train/test sets."""
    logging.info("Preparing training data...")
    
    # Load and clean dataset
    df = load_dataset(path)
    df = clean_data(df)
    df = feature_engineering(df)

    # Separate features and target
    X = df.drop(columns=[target_column])
    y = df[target_column]

    # Ensure classification labels remain discrete
    y = y.astype(int)

    # Handle class imbalance using SMOTE
    logging.info("Applying SMOTE to handle class imbalance...")
    X, y = handle_class_imbalance(X, y)

    # Split data into train and test sets
    logging.info("Splitting data into train and test sets...")
    X_train, X_test, y_train, y_test = split_data(X, y, test_size=test_size, random_state=random_state)

    # Scale features
    logging.info("Scaling feature matrices...")
    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_test = scaler.transform(X_test)

    return X_train, X_test, y_train, y_test, scaler
