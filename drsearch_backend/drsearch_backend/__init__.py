import importlib, sys
# Map drsearch_backend.app to the existing top-level 'app' package
sys.modules[__name__ + '.app'] = importlib.import_module('app')
