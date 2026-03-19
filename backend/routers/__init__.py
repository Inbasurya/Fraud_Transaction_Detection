from routers.transactions import router as transactions_router
from routers.alerts import router as alerts_router
from routers.dashboard import router as dashboard_router
from routers.customers import router as customers_router
from routers.ws import router as ws_router

__all__ = [
    "transactions_router",
    "alerts_router",
    "dashboard_router",
    "customers_router",
    "ws_router",
]
