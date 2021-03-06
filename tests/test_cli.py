import base64
import os
import getpass
import json
import shutil
from click.testing import CliRunner
import unittest
from pitcrew.cli import cli


class TestCli(unittest.TestCase):
    def test_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["help"])
        self.assertEqual(result.exit_code, 0)
        self.assertTrue("Commands" in result.output)
        self.assertTrue("Usage" in result.output)
        self.assertTrue("Options" in result.output)

    def test_docs(self):
        with open("docs/tasks.md") as fh:
            expected_docs = fh.read()
        os.remove("docs/tasks.md")
        runner = CliRunner()
        result = runner.invoke(cli, ["docs"])
        self.assertEqual(result.exit_code, 0)
        with open("docs/tasks.md") as fh:
            actual_docs = fh.read()
            self.assertEqual(actual_docs, expected_docs)

    def test_info(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["info", "fs.write"])
        self.assertEqual(result.exit_code, 0)
        self.assertTrue("fs.write\n" in result.output)

    def test_list(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["list"])
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(len(result.output.split("\n")) > 10)

    def test_new(self):
        task_path = os.path.abspath(
            os.path.join(
                __file__,
                "..",
                "..",
                "pitcrew",
                "tasks",
                "some",
                "kind",
                "of",
                "task.py",
            )
        )
        try:
            runner = CliRunner()
            result = runner.invoke(cli, ["new", "some.kind.of.task"])
            self.assertEqual(result.exit_code, 0)
            self.assertTrue(os.path.isfile(task_path))
        finally:
            os.remove(task_path)

    def test_new_rename(self):
        base_path = os.path.abspath(
            os.path.join(__file__, "..", "..", "pitcrew", "tasks")
        )
        try:
            runner = CliRunner()
            result = runner.invoke(cli, ["new", "some.kind.of.task"])
            self.assertEqual(result.exit_code, 0)
            self.assertTrue(os.path.isfile(base_path + "/some/kind/of/task.py"))
            result = runner.invoke(cli, ["new", "some.kind.of.task.lower"])
            self.assertEqual(result.exit_code, 0)
            self.assertFalse(os.path.isfile(base_path + "/some/kind/of/task.py"))
            self.assertTrue(
                os.path.isfile(base_path + "/some/kind/of/task/__init__.py")
            )
            self.assertTrue(os.path.isfile(base_path + "/some/kind/of/task/lower.py"))
        finally:
            shutil.rmtree(base_path + "/some/kind")

    def test_run(self):
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(cli, ["run", "fs.read", "requirements.txt"])
        self.assertEqual(result.exit_code, 0)

        with open("requirements.txt", "r") as fh:
            expected_output = json.dumps(
                [
                    {
                        "context": f"{getpass.getuser()}@local",
                        "result": fh.read(),
                        "exception": None,
                    }
                ]
            )
            self.assertEqual(result.stdout_bytes.decode(), expected_output)

    def test_run_with_binary(self):
        base64_data = "CUGhip285YEjnHE4Cel0/lA5OLPV5gEsuEGMEfR7"
        with open("test_data", "wb") as fh:
            fh.write(base64.b64decode(base64_data))
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(cli, ["run", "fs.read", "test_data"])
        self.assertEqual(result.exit_code, 0)
        expected_output = json.dumps(
            [
                {
                    "context": f"{getpass.getuser()}@local",
                    "result": base64_data,
                    "exception": None,
                }
            ]
        )
        self.assertEqual(result.stdout_bytes.decode(), expected_output)

    def test_test(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["test", "fs.digests.md5"])
        self.assertEqual(result.exit_code, 0)
