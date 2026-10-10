import tempfile
import unittest
from pathlib import Path

from pitwall.imports import importers, specifiers

FILES = {
    "src/lib/cart.ts": "export const total = 1\n",
    "src/components/CartSummary.tsx": "import { total } from '../lib/cart'\nimport x from 'react'\n",
    "src/app/page.tsx": "import CartSummary from '@/components/CartSummary'\nconst y = await import('./util')\n",
    "src/app/util/index.js": "module.exports = require('../../lib/cart.ts')\n",
    "tests/cart.test.ts": "import { total } from '../src/lib/cart'\n",
    "api/routes.py": "from .db import session\nfrom shop.models import Cart\nimport os\n",
    "api/db.py": "session = None\n",
    "api/__init__.py": "",
    "shop/models.py": "class Cart: pass\n",
    "shop/__init__.py": "",
    "shop/cli.py": "from shop import models, helpers\nfrom . import models as m\n",
}


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for rel, text in FILES.items():
            (self.root / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.root / rel).write_text(text)
        self.index = importers(self.root, list(FILES))

    def tearDown(self):
        self.tmp.cleanup()

    def test_specifiers(self):
        self.assertEqual(specifiers("a.ts", "import a from './a'\nexport * from \"./b\"\nimport './c.css'\n"),
                         ["./a", "./b", "./c.css"])

    def test_js_and_ts_importers(self):
        self.assertEqual(sorted(self.index["src/lib/cart.ts"]),
                         ["src/app/util/index.js", "src/components/CartSummary.tsx", "tests/cart.test.ts"])

    def test_alias_and_index_files(self):
        self.assertEqual(self.index["src/components/CartSummary.tsx"], ["src/app/page.tsx"])
        self.assertEqual(self.index["src/app/util/index.js"], ["src/app/page.tsx"])

    def test_python_relative_and_package_imports(self):
        self.assertEqual(self.index["api/db.py"], ["api/routes.py"])
        self.assertIn("api/routes.py", self.index["shop/models.py"])

    def test_from_package_import_module_points_at_the_module(self):
        self.assertIn("shop/cli.py", self.index["shop/models.py"])
        self.assertIn("shop/cli.py", self.index["shop/__init__.py"])  # helpers is not a module: the package

    def test_packages_outside_the_repo_are_ignored(self):
        self.assertNotIn("react", self.index)


if __name__ == "__main__":
    unittest.main()
