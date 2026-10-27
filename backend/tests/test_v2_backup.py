import tempfile,sqlite3,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
from backup_sqlite import backup
class BackupTests(unittest.TestCase):
    def test_integrity_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            source=Path(temp)/'source.db';dest=Path(temp)/'backup.db'
            with sqlite3.connect(source) as db:db.execute('create table cursors (sequence integer)');db.execute('insert into cursors values (42)')
            self.assertEqual(backup(source,dest)['integrity_check'],'ok')
            with sqlite3.connect(dest) as db:self.assertEqual(db.execute('select sequence from cursors').fetchone()[0],42)
            with self.assertRaises(ValueError):backup(source,dest)
