import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import lab


class LabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.binary=Path(cls.temp.name)/'controller'
        lab.build(cls.binary)
        cls.cases,_=lab.load_scenarios(lab.ROOT/'scenarios/regression.json')

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def test_all_regression_scenarios(self):
        for case in self.cases:
            with self.subTest(case=case['name']):
                result=lab.run_scenario(self.binary,case)
                self.assertTrue(result['passed'],result['errors'])

    def test_wrong_expectation_fails(self):
        case=copy.deepcopy(self.cases[0]);case['steps'][0]['expect']['permit']=True
        self.assertFalse(lab.run_scenario(self.binary,case)['passed'])

    def test_parser_rejects_malformed_frames(self):
        for line in ['','-1 1 1 400 1 H','4294967296 1 1 400 1 H','0 2 1 400 1 H',
                     '0 1 1 40000 1 H','0 1 1 400 1 HH','0 1 1 400 1 H extra','bad']:
            with self.subTest(line=line):
                run=subprocess.run([str(self.binary)],input=line+'\n',text=True,capture_output=True)
                self.assertEqual(run.returncode,2)

    def test_unknown_command_reaches_controller_fault(self):
        run=subprocess.run([str(self.binary)],input='0 1 1 400 1 ?\n',text=True,capture_output=True,check=True)
        self.assertEqual(json.loads(run.stdout)['faults'],64)

    def test_scenario_validation(self):
        for change in [{'time_ms':True},{'fresh':1},{'value':40000},{'command':'\n'},
                       {'expect':{'state':[],'permit':False,'faults':0}}]:
            data=dict(schema_version=1,scenarios=copy.deepcopy(self.cases[:1]))
            data['scenarios'][0]['steps'][0].update(change)
            with tempfile.TemporaryDirectory() as tmp:
                path=Path(tmp)/'bad.json';path.write_text(json.dumps(data))
                with self.subTest(change=change),self.assertRaises(ValueError):lab.load_scenarios(path)

    def test_duplicate_names_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'bad.json';path.write_text(json.dumps(dict(schema_version=1,scenarios=[self.cases[0],self.cases[0]])))
            with self.assertRaises(ValueError):lab.load_scenarios(path)

    def test_report_escapes_content_and_junit_matches_failures(self):
        result=lab.run_scenario(self.binary,self.cases[0])
        result['purpose']='<script>alert(1)</script>'
        result['passed']=False;result['errors']=['deliberate test failure']
        report=dict(generated_at='2026-10-22T00:00:00+00:00',core_sha256='test',results=[result])
        with tempfile.TemporaryDirectory() as tmp:
            lab.write_reports(tmp,report)
            document=(Path(tmp)/'report.html').read_text()
            self.assertNotIn('<script>',document)
            self.assertIn('&lt;script&gt;',document)
            root=ET.parse(Path(tmp)/'junit.xml').getroot()
            self.assertEqual(root.attrib['failures'],'1')
            self.assertEqual(len(root.findall('testcase/failure')),1)

    def test_missing_compiler_is_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            result=lab.main(['--cxx',str(Path(tmp)/'missing-compiler'),'--out',tmp])
            self.assertEqual(result,2)

    def test_cli_exit_code_and_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'wrong.json'
            data=dict(schema_version=1,scenarios=copy.deepcopy(self.cases[:1]))
            data['scenarios'][0]['steps'][0]['expect']['permit']=True
            path.write_text(json.dumps(data))
            run=subprocess.run([sys.executable,str(lab.ROOT/'lab.py'),'--scenarios',str(path),'--out',tmp],capture_output=True,text=True,timeout=15)
            self.assertEqual(run.returncode,1,run.stderr)
            report=json.loads((Path(tmp)/'report.json').read_text())
            self.assertFalse(report['results'][0]['passed'])


if __name__=='__main__':unittest.main()
