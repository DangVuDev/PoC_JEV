from .base import ProviderAdapter
from .jev_native import JevNativeAdapter
from .noul_decomposition import NoulDecompositionAdapter

ADAPTERS: dict[str, ProviderAdapter] = {
    JevNativeAdapter.strategy: JevNativeAdapter(),
    NoulDecompositionAdapter.strategy: NoulDecompositionAdapter(),
}

__all__ = ["ADAPTERS", "JevNativeAdapter", "NoulDecompositionAdapter", "ProviderAdapter"]
