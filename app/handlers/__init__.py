from .common import router as common_router
from .nst import router as nst_router
from .cyclegan import router as cyclegan_router

all_routers = [
    nst_router,
    cyclegan_router,
    # other_specific_router,
    common_router,
]
