"""A cave repo's config: one JSON file listing its caves and, for each, where
its survey, names, ground, drawn survey and walls come from. See
caveviewer/schema.json for every key, and README.md for examples.

Paths in the config are relative to the config file's own folder (the cave
repo). A cave is its own entry deep-merged over the file's "defaults", so
what all of a repo's caves share is said once.
"""
import copy
import json
import os

SURVEYS = ('therion', 'survex')
TERRAINS = ('ea', 'wales', 'flat')
DRAWN = ('therion-svg', 'scan', 'none')
FEATURES = ('routes', 'drawn', 'walls', 'ar', 'offline')

# what a cave has where neither it nor the defaults say
BASE = {
    'area': '',
    'credit': '',
    'grid': {'offset': [0, 0]},
    'survey': {'type': 'survex'},
    'names': {},
    'routing': {'duplicates': True, 'join': 3.0, 'codes_first': True, 'snap': 15},
    'terrain': {'type': 'flat', 'step': 2, 'margin': 250, 'align': 100, 'cache': 'lidar'},
    'drawn': {'type': 'none'},
    'walls': None,
    'georef': {},
    'features': {f: True for f in FEATURES},
}


class ConfigError(ValueError):
    pass


def merge(a, b):
    """b over a, recursing into objects (lists and everything else replace)."""
    if not isinstance(a, dict) or not isinstance(b, dict):
        return copy.deepcopy(b)
    out = copy.deepcopy(a)
    for k, v in b.items():
        out[k] = merge(out[k], v) if k in out and isinstance(out[k], dict) and isinstance(v, dict) else copy.deepcopy(v)
    return out


class Config:
    def __init__(self, path):
        self.path = os.path.abspath(path)
        self.root = os.path.dirname(self.path)
        raw = json.load(open(self.path, encoding='utf-8'))
        if not isinstance(raw.get('caves'), list) or not raw['caves']:
            raise ConfigError(f'{path}: "caves" must be a list of at least one cave')
        self.raw = raw
        self.work = self.at(raw.get('work', 'build'))
        defaults = merge(BASE, raw.get('defaults', {}))
        self.caves = [self._cave(merge(defaults, c), i) for i, c in enumerate(raw['caves'])]
        ids = [c['id'] for c in self.caves]
        if len(set(ids)) != len(ids):
            raise ConfigError(f'{path}: cave ids must differ ({ids})')
        site = raw.get('site', {})
        self.site = {'index': len(self.caves) > 1, 'title': 'Caves in 3D', 'description': '', 'lede': '', 'footer': '{credits}', **site}

    def at(self, p):
        """A config path, made absolute."""
        return p if p is None or os.path.isabs(p) else os.path.normpath(os.path.join(self.root, p))

    def _cave(self, c, i):
        where = f'{self.path}: caves[{i}]'
        for k in ('id', 'name'):
            if not c.get(k):
                raise ConfigError(f'{where}: "{k}" is required')
        for key, kinds in (('survey', SURVEYS), ('terrain', TERRAINS), ('drawn', DRAWN)):
            if c[key].get('type') not in kinds:
                raise ConfigError(f'{where}: {key}.type must be one of {", ".join(kinds)} (not {c[key].get("type")!r})')
        unknown = set(c['features']) - set(FEATURES)
        if unknown:
            raise ConfigError(f'{where}: unknown features {sorted(unknown)}')
        if c['survey']['type'] == 'therion':
            for k in ('checkout', 'dir', 'source'):
                if not c['survey'].get(k):
                    raise ConfigError(f'{where}: survey.{k} is required for a Therion survey')
        elif c['drawn']['type'] == 'therion-svg' and not c['drawn'].get('svg'):
            raise ConfigError(f'{where}: a therion-svg drawn survey needs a Therion survey, or drawn.svg (a plan Therion has drawn)')
        if c['survey']['type'] == 'survex' and not c['survey'].get('file'):
            raise ConfigError(f'{where}: survey.file (a Survex .3d) is required')
        if c['drawn']['type'] == 'scan':
            for k in ('image', 'fit'):
                if not c['drawn'].get(k):
                    raise ConfigError(f'{where}: drawn.{k} is required for a scanned drawing')
        c.setdefault('path', c['id'])
        return c

    def work_dir(self, cave):
        """Where the cave's intermediate files go (cave.3d, names.json, plan.svg, ...)."""
        return os.path.join(self.work, cave['id'])

    def centreline(self, cave):
        if cave['survey']['type'] == 'therion':
            return os.path.join(self.work_dir(cave), 'cave.3d')
        return self.at(cave['survey']['file'])
