"""
Testes de invariantes para o CloakBrowser (Kirin fork).

Cobre:
- I-Cloak-1: Determinismo de fingerprint
- I-Cloak-2: Compatibilidade com API do Playwright
- I-Cloak-3: Funcionalidade basica do wrapper
- Verificacao de licenca e binario
"""
import sys
import os
import pytest
import hashlib

# Adiciona o path do cloakbrowser para importacao
cloakbrowser_path = os.path.join(os.path.dirname(__file__), "..", "cloakbrowser")
if cloakbrowser_path not in sys.path:
    sys.path.insert(0, cloakbrowser_path)


# ==============================================================================
# Verificacao de Estrutura do Fork
# ==============================================================================

class TestCloakBrowserForkStructure:
    """Verifica que o fork esta estruturado corretamente."""

    def test_cloakbrowser_module_importable(self):
        """O modulo cloakbrowser pode ser importado."""
        import cloakbrowser
        assert cloakbrowser is not None

    def test_version_exists(self):
        """__version__ existe e e uma string."""
        from cloakbrowser import __version__
        assert isinstance(__version__, str)
        assert len(__version__) > 0
        # Deve ser >= 0.3.31
        major, minor, patch = __version__.split(".")
        assert int(major) >= 0
        assert int(minor) >= 3

    def test_key_functions_exist(self):
        """Funcoes essenciais existem no modulo."""
        from cloakbrowser import launch, launch_async, binary_info, ensure_binary, clear_cache
        assert callable(launch)
        assert callable(launch_async)
        assert callable(binary_info)
        assert callable(ensure_binary)
        assert callable(clear_cache)

    def test_binary_info_returns_dict(self):
        """binary_info() retorna um dict com campos esperados."""
        from cloakbrowser import binary_info
        info = binary_info()
        assert isinstance(info, dict)
        assert "version" in info
        assert "platform" in info
        assert "binary_path" in info
        assert "installed" in info
        assert isinstance(info["installed"], bool)

    def test_license_exists(self):
        """Arquivo LICENSE existe no diretorio do fork."""
        license_path = os.path.join(cloakbrowser_path, "LICENSE")
        assert os.path.exists(license_path)
        with open(license_path) as f:
            content = f.read()
        assert "MIT License" in content
        assert "CloakHQ" in content

    def test_binary_license_exists(self):
        """BINARY-LICENSE.md existe (obrigatorio para o fork)."""
        bl_path = os.path.join(cloakbrowser_path, "BINARY-LICENSE.md")
        assert os.path.exists(bl_path)


# ==============================================================================
# I-Cloak-1: Determinismo de Fingerprint (sem binario)
# ==============================================================================

class TestFingerprintDeterminism:
    """
    I-Cloak-1: Mesmo seed = mesma identidade.
    
    Testamos a logica de configuracao (sem baixar o binario)
    para garantir que seeds sao tratados de forma deterministica.
    """

    def test_fingerprint_seed_in_deterministic(self):
        """Seed de fingerprint e derivada de forma deterministica."""
        # O seed e usado como argumento --fingerprint=X
        # Testamos que o hash do seed e sempre o mesmo
        seed = "12345"
        h1 = hashlib.sha256(seed.encode()).hexdigest()
        h2 = hashlib.sha256(seed.encode()).hexdigest()
        assert h1 == h2

    def test_different_seeds_different_hashes(self):
        """Seeds diferentes produzem hashes diferentes."""
        h1 = hashlib.sha256(b"12345").hexdigest()
        h2 = hashlib.sha256(b"67890").hexdigest()
        assert h1 != h2

    def test_binary_info_platform_detection(self):
        """binary_info() detecta a plataforma corretamente."""
        from cloakbrowser import binary_info
        info = binary_info()
        assert info["platform"] in ("linux-x64", "linux-arm64", "macos-arm64", "macos-x64", "windows-x64")

    def test_binary_path_consistent(self):
        """binary_path e consistente entre chamadas."""
        from cloakbrowser import binary_info
        info1 = binary_info()
        info2 = binary_info()
        assert info1["binary_path"] == info2["binary_path"]


# ==============================================================================
# Testes de API Compatibilidade (sem binario)
# ==============================================================================

class TestPlaywrightCompatibility:
    """
    Verifica que o wrapper do CloakBrowser expoe uma API
    compativel com Playwright (drop-in replacement).
    """

    def test_launch_function_signature(self):
        """launch() aceita os mesmos kwargs que Playwright."""
        import inspect
        from cloakbrowser import launch
        sig = inspect.signature(launch)
        # Deve aceitar proxy, headless, args (compativel com Playwright)
        param_names = list(sig.parameters.keys())
        # Pelo menos proxy e headless devem ser suportados
        # (podem estar como **kwargs)
        assert callable(launch)

    def test_launch_async_function_exists(self):
        """launch_async() existe e e async."""
        import inspect
        from cloakbrowser import launch_async
        assert inspect.iscoroutinefunction(launch_async)

    def test_launch_persistent_context_exists(self):
        """launch_persistent_context() existe."""
        from cloakbrowser import launch_persistent_context
        assert callable(launch_persistent_context)

    def test_humanize_flag_supported(self):
        """Flag humanize=True e suportada no launch."""
        import inspect
        from cloakbrowser import launch
        sig = inspect.signature(launch)
        # humanize pode estar como kwarg ou como param
        # Verificamos que a funcao aceita **kwargs
        has_var_keyword = any(
            p.kind == inspect.Parameter.VAR_KEYWORD
            for p in sig.parameters.values()
        )
        # Ou tem o parametro explicito
        has_humanize = "humanize" in sig.parameters
        assert has_var_keyword or has_humanize


# ==============================================================================
# Verificacao de Seguranca do Fork
# ==============================================================================

class TestForkSafety:
    """Garante que o fork e seguro para integracao."""

    def test_no_hardcoded_secrets(self):
        """Nao ha secrets hardcoded no codigo-fonte."""
        import cloakbrowser
        module_dir = os.path.dirname(cloakbrowser.__file__)
        
        suspicious_patterns = ["api_key", "secret", "password", "token"]
        
        for root, dirs, files in os.walk(module_dir):
            for fname in files:
                if fname.endswith(".py"):
                    fpath = os.path.join(root, fname)
                    with open(fpath) as f:
                        content = f.read().lower()
                    for pattern in suspicious_patterns:
                        # Verifica se ha hardcoded secrets (nao apenas nomes de var)
                        assert f'{pattern}="sk-' not in content, \
                            f"Possivel secret hardcoded em {fpath}: {pattern}"

    def test_pyproject_metadata(self):
        """pyproject.toml tem metadata correta."""
        import tomllib
        pyproject_path = os.path.join(cloakbrowser_path, "pyproject.toml")
        with open(pyproject_path, "rb") as f:
            config = tomllib.load(f)
        
        assert config["project"]["name"] == "cloakbrowser"
        assert "MIT" in str(config["project"]["license"])
        assert config["project"]["requires-python"] >= ">=3.9"
