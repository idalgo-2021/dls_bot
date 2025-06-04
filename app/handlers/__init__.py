from .common import router as common_router
from .nst import router as nst_router

all_routers = [
    nst_router,
    # other_specific_router,
    common_router,
]
