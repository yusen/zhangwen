"""Mode overrides share the original local settings file, never project data."""
import json
from .models import AiSettingsInput
from .endpoints import DEFAULT_BASE_URL, resolve_settings

MODES = ('engineer', 'structure', 'learning')


def load(path, fallback):
    overrides = {}
    try:
        stored = json.loads(path.read_text(encoding='utf-8'))
        base = {key: value for key, value in stored.items() if key != 'modes'}
        valid = AiSettingsInput.model_validate(base)
        fallback = resolve_settings({'apiKey': '', 'baseUrl': valid.baseUrl or DEFAULT_BASE_URL}, valid)
        for mode, value in stored.get('modes', {}).items():
            if mode not in ('structure', 'learning'):
                continue
            try:
                request = AiSettingsInput.model_validate(value)
                overrides[mode] = resolve_settings({'apiKey': '', 'baseUrl': request.baseUrl or DEFAULT_BASE_URL}, request)
            except (ValueError, TypeError):
                continue
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    return fallback, overrides


def for_mode(state, mode):
    return state.ai_mode_settings.get(mode, state.ai_settings) if mode != 'engineer' else state.ai_settings
