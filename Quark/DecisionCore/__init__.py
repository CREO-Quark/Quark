import abc
import json
import os.path
import pathlib
import re

from AlgoEngine.Engine import PositionManagementService

from .. import LOGGER

LOGGER = LOGGER.getChild('DecisionCore')


class DecisionCore(object, metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def predict(self, factor_value: dict[str, float], timestamp: float) -> dict[str, float]:
        ...

    @abc.abstractmethod
    def signal(self, position: PositionManagementService, prediction: dict[str, float], timestamp: float) -> int:
        ...

    @abc.abstractmethod
    def trade_volume(self, position: PositionManagementService, cash: float, margin: float, timestamp: float, signal: int) -> float:
        ...

    @abc.abstractmethod
    def calibrate(self, *args, **kwargs):
        ...

    @abc.abstractmethod
    def validation(self, *args, **kwargs):
        ...

    @abc.abstractmethod
    def clear(self):
        ...

    @abc.abstractmethod
    def to_json(self, fmt='dict') -> dict | str:
        ...

    @classmethod
    @abc.abstractmethod
    def from_json(cls, json_str: str | bytes | dict):
        ...

    def dump(self, file_path: str | pathlib.Path = None):
        json_dict = self.to_json(fmt='dict')
        json_str = json.dumps(json_dict, indent=4)

        if file_path is not None:
            with open(file_path, 'w') as f:
                f.write(json_str)

        return json_dict

    @classmethod
    def load(cls, file_path: str | pathlib.Path = None, file_pattern: str | re.Pattern = None, file_dir: str | pathlib.Path = None):
        if file_path is not None:

            if os.path.isfile(file_path):
                with open(file_path, 'r') as f:
                    json_dict = json.load(f)
                return cls.from_json(json_dict)

            raise FileNotFoundError(f'{file_path} does not exist!')

        if file_pattern is not None:
            if not os.path.isdir(file_dir):
                raise FileNotFoundError(f'{file_dir} does not exist!')

            for file_name in sorted(os.listdir(file_dir), reverse=True):
                if re.match(file_pattern, file_name):
                    if file_dir is None:
                        file_path = os.path.realpath(file_name)
                    else:
                        file_path = os.path.realpath(pathlib.Path(file_dir, file_name))

                    LOGGER.info(f'loading {cls.__name__} from {file_path}...')

                    return cls.load(file_path=file_path)

            if file_dir is None:
                raise FileNotFoundError(f'{file_pattern} does not exist!')
            else:
                raise FileNotFoundError(f'{file_pattern} does not exist at {os.path.realpath(file_dir)}!')

    @property
    @abc.abstractmethod
    def is_ready(self):
        ...


class DummyDecisionCore(DecisionCore):

    def predict(self, factor_value: dict[str, float], timestamp: float) -> dict[str, float]:
        return {}

    def signal(self, position: PositionManagementService, prediction: dict[str, float], timestamp: float) -> int:
        return 0

    def trade_volume(self, position: PositionManagementService, cash: float, margin: float, timestamp: float, signal: int) -> float:
        return 1.

    def calibrate(self, *args, **kwargs) -> dict:
        """
        calibrate decision core and gives a calibration report, in dict (like json)
        """
        pass

    def validation(self, *args, **kwargs):
        pass

    def clear(self):
        pass

    def to_json(self, fmt='dict') -> dict | str:
        pass

    @classmethod
    def from_json(cls, json_str: str | bytes | dict):
        pass

    @property
    def is_ready(self):
        return True


from .decision_core import MajorityDecisionCore

__all__ = ['DecisionCore', 'DummyDecisionCore', 'MajorityDecisionCore']
