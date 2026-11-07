from pathlib import Path
import tempfile
import unittest

from PoemReciter import PoemReciter
from poem_reciter.models import EvaluationResult
from poem_reciter.repository import FilePoemRepository, normalize_poem_text, parse_header
from poem_reciter.service import ReciterService

try:
    from poem_reciter.app import create_app
    HAS_FLASK = True
except ModuleNotFoundError:
    HAS_FLASK = False

PROJECT_ROOT = Path(__file__).resolve().parent.parent
POEMS_FILE = PROJECT_ROOT / "Poems"


class TestNormalizationAndParsing(unittest.TestCase):
    def test_normalize_poem_text_trims_lines_and_blank_edges(self):
        raw = "  \n  春眠不觉晓 \r\n 处处闻啼鸟\n夜来风雨声  \n 花落知多少 \n\n "
        expected = "春眠不觉晓\n处处闻啼鸟\n夜来风雨声\n花落知多少"
        self.assertEqual(normalize_poem_text(raw), expected)

    def test_parse_header_with_dynasty(self):
        title, dynasty, author = parse_header("江亭夜月送别 【唐】王勃")
        self.assertEqual((title, dynasty, author), ("江亭夜月送别", "唐", "王勃"))

    def test_parse_header_without_space_before_dynasty(self):
        title, dynasty, author = parse_header("思帝乡.春日游【唐】韦庄")
        self.assertEqual((title, dynasty, author), ("思帝乡.春日游", "唐", "韦庄"))

    def test_parse_header_without_dynasty(self):
        title, dynasty, author = parse_header("浪淘沙.北戴河 毛泽东")
        self.assertEqual((title, dynasty, author), ("浪淘沙.北戴河", None, "毛泽东"))


class TestRepositoryAndService(unittest.TestCase):
    def setUp(self):
        self.repo = FilePoemRepository(POEMS_FILE)
        self.service = ReciterService(self.repo)

    def test_loads_all_poems_from_file(self):
        poems = self.service.get_all_poems()
        self.assertEqual(len(poems), 100)
        first = self.service.get_poem(1)
        self.assertIsNotNone(first)
        self.assertEqual(first.header, "江亭夜月送别 【唐】王勃")
        self.assertEqual(
            first.text,
            "乱烟笼碧砌\n飞月向南端\n寂寞离亭掩\n江山此夜寒",
        )

    def test_whitespace_trimmed_on_poem_32_and_42(self):
        poem_32 = self.service.get_poem(32)
        self.assertFalse(poem_32.lines[0].startswith(" "))
        poem_42 = self.service.get_poem(42)
        self.assertFalse(poem_42.lines[-1].endswith(" "))

    def test_evaluate_correct_with_extra_whitespace(self):
        poem = self.service.get_poem(1)
        user_input = "\n  乱烟笼碧砌  \n飞月向南端\n 寂寞离亭掩 \n江山此夜寒  \n"
        result = self.service.evaluate(poem.id, user_input)
        self.assertTrue(result.is_correct)
        self.assertTrue(all(lc.is_correct for lc in result.line_comparisons))

    def test_evaluate_incorrect_and_listener_hook(self):
        recorded: list[EvaluationResult] = []
        self.service.register_attempt_listener(recorded.append)

        result = self.service.evaluate(
            1,
            "乱烟笼碧砌\n飞月向北端\n寂寞离亭掩\n江山此夜寒",
        )
        self.assertFalse(result.is_correct)
        self.assertEqual(len(result.line_comparisons), 4)
        self.assertTrue(result.line_comparisons[0].is_correct)
        self.assertFalse(result.line_comparisons[1].is_correct)
        self.assertEqual(result.line_comparisons[1].expected, "飞月向南端")
        self.assertEqual(result.line_comparisons[1].actual, "飞月向北端")
        self.assertEqual(len(recorded), 1)
        self.assertEqual(recorded[0], result)

    def test_pick_random_poem_excludes_id(self):
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".txt", delete=False) as tf:
            tf.write("诗一 【唐】甲：第一句\\n第二句\n")
            tf.write("诗二 【唐】乙：第三句\\n第四句\n")
            temp_path = Path(tf.name)
        try:
            small_service = ReciterService(FilePoemRepository(temp_path))
            for _ in range(10):
                picked = small_service.pick_random_poem(exclude_id=1)
                self.assertEqual(picked.id, 2)
        finally:
            temp_path.unlink(missing_ok=True)

    def test_console_poem_reciter_compatibility(self):
        pr = PoemReciter()
        pr.loadPoems()
        self.assertEqual(len(pr.poems), 100)
        self.assertIn(pr.poemName, pr.poems)


@unittest.skipUnless(HAS_FLASK, "Flask is not installed in the current Python environment")
class TestFlaskApp(unittest.TestCase):
    def setUp(self):
        app = create_app(poems_path=POEMS_FILE)
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_index_route(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("诗词背诵", resp.get_data(as_text=True))

    def test_health_endpoint(self):
        resp = self.client.get("/api/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["total_poems"], 100)

    def test_random_poem_endpoint(self):
        resp = self.client.get("/api/poems/random")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("id", data)
        self.assertIn("header", data)
        self.assertNotIn("text", data)

    def test_check_poem_endpoint(self):
        correct_resp = self.client.post(
            "/api/poems/1/check",
            json={"answer": "乱烟笼碧砌\n飞月向南端\n寂寞离亭掩\n江山此夜寒"},
        )
        self.assertEqual(correct_resp.status_code, 200)
        self.assertTrue(correct_resp.get_json()["is_correct"])

        wrong_resp = self.client.post(
            "/api/poems/1/check",
            json={"answer": "乱烟笼碧砌"},
        )
        self.assertEqual(wrong_resp.status_code, 200)
        self.assertFalse(wrong_resp.get_json()["is_correct"])


if __name__ == "__main__":
    unittest.main()
