import pickle
import logging
from typing import Any

logger = logging.getLogger(__name__)

class ObjectOperation:
    """
    Utility class for saving and loading objects to/from disk using pickle.
    """
    @staticmethod
    def save(obj: Any, filename: str) -> None:
        """
        Save the object to disk.
        Args:
            obj (Any): The object to save.
            filename (str): The file path to save the object.
        """
        try:
            with open(filename, 'wb') as f:
                pickle.dump(obj, f)
        except Exception as e:
            logger.error(f"Failed to save object to {filename}: {e}")
            raise

    @staticmethod
    def load(filename: str) -> Any:
        """
        Load the object from disk.
        Args:
            filename (str): The file path to load the object from.
        Returns:
            Any: The loaded object.
        Raises:
            FileNotFoundError: If the file does not exist.
            Exception: If loading fails for other reasons.
        """
        try:
            with open(filename, 'rb') as f:
                obj = pickle.load(f)
            return obj
        except FileNotFoundError:
            logger.error(f"File {filename} not found.")
            raise FileNotFoundError(f"File {filename} not found")
        except Exception as e:
            logger.error(f"Failed to load object from {filename}: {e}")
            raise