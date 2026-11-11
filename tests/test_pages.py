"""Landing pages: which caves are below which, and Therion's survey list read."""
import os
import tempfile
import unittest

from caveviewer.files import survey_list
from caveviewer.pages import children, inside

LIST = '''<table><tr><th>Title</th></tr>
<tr id="Area"><td><a href="x">Area<br>Somewhere</a></td><td>100</td><td>50</td><td>0</td><td>0</td><td>0</td><td>0</td><td>40</td><td>41</td></tr>
<tr id="Area.Small"><td><a href="x">Small Hole</a></td><td>10</td><td>5</td><td>0</td><td>0</td><td>0</td><td>0</td><td>4</td><td>5</td></tr>
<tr id="Area.Big"><td><a href="x">Big</a></td><td>90.4</td><td>45</td><td>0</td><td>0</td><td>0</td><td>0</td><td>36</td><td>37</td></tr>
<tr id="Area.Big.Bit"><td>Bit</td><td>20</td><td>3</td><td>0</td><td>0</td><td>0</td><td>0</td><td>8</td><td>9</td></tr>
</table>'''


class Pages(unittest.TestCase):
    def test_inside(self):
        self.assertTrue(inside('.', 'gb'))
        self.assertTrue(inside('mendip', 'mendip/gb'))
        self.assertFalse(inside('gb', 'gb'))
        self.assertFalse(inside('gb', 'gbx'))

    def test_children_skip_grandchildren(self):
        caves = [{'page': '.'}, {'page': 'a'}, {'page': 'a/b'}, {'page': 'c'}, {'id': 'no page'}]
        self.assertEqual(children(caves[0], caves), [caves[1], caves[3]])
        self.assertEqual(children(caves[1], caves), [caves[2]])

    def test_survey_list(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'list.html')
            open(p, 'w').write(LIST)
            top, kids = survey_list(p)
        self.assertEqual((top['title'], top['length'], top['stations']), ('Area', 100, 41))
        self.assertEqual([(k['id'], k['title'], k['length']) for k in kids], [('Big', 'Big', 90), ('Small', 'Small Hole', 10)])


if __name__ == '__main__':
    unittest.main()
