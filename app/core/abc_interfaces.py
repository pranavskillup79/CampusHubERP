from abc import ABC, abstractmethod

from app.core.metaclasses import AuditMeta


# Every person model must display and export its own details.
class Person(ABC, metaclass=AuditMeta):
    @abstractmethod
    def display_details(self):
        pass

    @abstractmethod
    def to_dict(self):
        pass
