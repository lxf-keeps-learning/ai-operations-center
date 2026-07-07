from abc import ABC, abstractmethod

from app.integrations.ioc.schema import IocApiResponse


class IocApiClient(ABC):
    """IOC 业务系统访问契约。

    Sprint3 的核心边界是：Query Tool 只依赖这个抽象，不关心数据来自 Mock
    还是真实 IOC API。后续接真实系统时新增 RealIocApiClient，并保持这些方法
    的入参和 IocApiResponse 返回结构稳定，Tool 层就不需要大改。
    """

    @abstractmethod
    def get_kpis(self, filters: dict | None = None) -> IocApiResponse:
        pass

    @abstractmethod
    def get_alarms(self, filters: dict | None = None) -> IocApiResponse:
        pass

    @abstractmethod
    def get_risks(self, filters: dict | None = None) -> IocApiResponse:
        pass

    @abstractmethod
    def get_work_orders(self, filters: dict | None = None) -> IocApiResponse:
        pass
