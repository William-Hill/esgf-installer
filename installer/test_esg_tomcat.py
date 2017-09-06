#!/usr/bin/local/env python

import unittest
import esg_tomcat_manager
import os
import shutil
import yaml

with open('esg_config.yaml', 'r') as config_file:
    config = yaml.load(config_file)

class test_ESG_tomcat(unittest.TestCase):

    @classmethod
    def tearDownClass(cls):
        try:
            os.remove("/tmp/apache-tomcat-8.5.20.tar.gz")
        except OSError, error:
            print "error:", error
            pass
        try:
            os.unlink("/usr/local/tomcat")
        except OSError, error:
            print "error:", error
            # shutil.unlink()
            pass

    # def test_download_tomcat(self):
    #     esg_tomcat_manager.download_tomcat()
    #     self.assertTrue(os.path.isfile("/tmp/apache-tomcat-8.5.20.tar.gz"))

    def test_main(self):
        esg_tomcat_manager.main()
        self.assertTrue(os.path.isdir("/usr/local/tomcat"))





if __name__ == '__main__':
    unittest.main()