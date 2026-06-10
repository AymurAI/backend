import yaml


def load_yaml(file_path: str) -> dict:
    """
    Loads a yaml file and returns its content as a dictionary.

    Args:
        file_path (str): The path to the yaml file.

    Returns:
        dict: The yaml file content.
    """
    with open(file_path, "r") as f:
        content = yaml.safe_load(f)
        return content


def save_yaml(dict_data: dict, file_path: str) -> None:
    """
    Saves a dictionary as a yaml file.

    Args:
        dict_data (dict): The dictionary to be saved.
        file_path (str): The path to the file where the yaml will be saved.
    """
    with open(file_path, "w") as f:
        f.write(yaml.dump(dict_data))
