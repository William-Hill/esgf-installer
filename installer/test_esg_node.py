import unittest
import esg_node
import os
import sys
import pprint


class test_ESG_Node(unittest.TestCase):
	def setUp(self):
		self.bit_boolean_dictionary = {"INSTALL_BIT": False , "TEST_BIT": False, "DATA_BIT":False, "INDEX_BIT":False, "IDP_BIT":False, "COMPUTE_BIT":False, "WRITE_ENV_BIT":False}
		self.node_type_list = ["data", "index"]
	def test_check_selected_node_type(self):
		found_valid_type = esg_node.check_selected_node_type(self.bit_boolean_dictionary, self.node_type_list)
		self.assertTrue(found_valid_type, True)



if __name__ == '__main__':
    unittest.main()