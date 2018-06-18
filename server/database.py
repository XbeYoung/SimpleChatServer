from multiprocessing import Lock
from threading import Timer
from user import *
from utils import use_log
import json
import os
import shutil

__all__ = ['Database']


class Database(object):

    def __init__(self):
        raise Exception('please use Database.create_db')

    def query_user_pwd(self, user_id: str, pwd: str) -> bool:
        pass

    def query_user(self, user_id: str):
        pass

    def add_user(self, user: User, pwd: str):
        pass

    def close(self):
        pass

    def data_changed(self):
        pass

    def distribution_id(self):
        pass

    def _storage(self):
        pass

    def _load(self):
        pass

    @staticmethod
    def create_db(sql_url=None, file_path=None):
        db = None
        try:
            db = SQLDatabase(sql_url)
        except Exception as e:
            db = FileDatabase(file_path)
        return db


class FileDatabase(Database):
    """
        使用文件持久化
    """
    _l = Lock()
    __instance = None
    __inited = False

    PWD_DB_NAME = 'pwd.dat'
    INFO_DB_NAME = 'info.dat'
    DIST_DB_NAME = 'dist.dat'

    def __new__(cls, *args, **kwargs):
        if not cls.__instance:
            cls.__instance = super().__new__(cls)
        return cls.__instance

    def __init__(self, base_dir='./database'):
        self._l.acquire()
        if not self.__inited:
            self.__inited = True
            self._changed = False
            self._user_pwd_table = {}
            self._user_info_table = {}
            self._nick_table = {}
            self._base_dir = base_dir and base_dir or './database'
            self._pwd_file = None
            self._info_file = None
            self._dist_file = None
            self._dist_id = 10000
            self._sync_exit = False
            self._timer = None
            self._load()
            self._l.release()
            # 释放锁，防止死锁
            self.__sync_backup_disk()
        else:
            self._l.release()

    @use_log
    def close(self):
        self._timer.cancel()
        self._disk_sync()
        self._user_pwd_table.clear()
        self._user_info_table.clear()
        self._nick_table.clear()

    def check_user_pwd(self, user_id: str, pwd: str) -> bool:
        """ 检查用户名和密码 """
        if self._user_pwd_table.get(user_id) != pwd:
            return False
        return True

    def modify_pwd(self, user_id, old_pwd, new_pwd) -> bool:
        if self.check_user_pwd(user_id, old_pwd):
            self._user_pwd_table[user_id] = new_pwd
            return True
        return False

    def query_user(self, user_id: str):
        """ 查询用户信息 """
        return self._user_info_table.get(user_id)

    def find_user4id(self, user_id: str, fuzzy=False) -> list:
        """ 查找好友 """
        if not fuzzy:
            user = self._user_info_table.get(user_id)
            return user and [user] or []
        else:
            result = []
            for key in self._user_info_table.keys():
                if user_id in key:
                    result.append(self._user_info_table.get(key))
            return result

    def find_user4nickname(self, nick_name, fuzzy=False) -> list:
        """ 使用昵称查询用户 """
        if not fuzzy:
            users = self._nick_table.get(nick_name)
            return users and users or []
        else:
            result = []
            for key in self._nick_table.keys():
                if nick_name in key:
                    result.extend(self._nick_table.get(nick_name))
            return result

    def add_user(self, user: User, pwd: str):
        """ 添加一个用户, 添加前请查询用户是否存在，该方法不予检查 """
        self._l.acquire()
        self._user_info_table[user.ID] = user
        self._user_pwd_table[user.ID] = pwd
        self._add_user2nick_table(user)
        self._changed = True
        self._l.release()
        print('DB add user --> %s' % user)

    def data_changed(self):
        """ 设置数据更新 """
        self._l.acquire()
        self._changed = True
        self._l.release()

    def distribution_id(self):
        ret = None
        self._l.acquire()
        ret = self._dist_id
        self._dist_id += 1
        # 同步写入文件
        self._dist_file.truncate(0)
        self._dist_file.seek(0)
        json.dump(self._dist_id, self._dist_file)
        self._dist_file.flush()
        self._l.release()
        return str(ret)

    @use_log
    def _disk_sync(self):
        """ 同步信息到磁盘 """
        self._l.acquire()
        if self._changed:
            self._storage()
        self._changed = False
        self._l.release()

    def _storage(self):
        """ 将文件信息写入磁盘 """
        self._pwd_file.truncate(0)
        self._info_file.truncate(0)
        self._dist_file.truncate(0)
        self._pwd_file.seek(0)
        self._info_file.seek(0)
        self._dist_file.seek(0)
        json.dump(self._dist_id, self._dist_file)
        json.dump(self._user_pwd_table, self._pwd_file)
        json.dump(self._user_info_table, self._info_file, default=Storable.encode)
        self._info_file.flush()
        self._pwd_file.flush()
        self._dist_file.flush()

    def _add_user2nick_table(self, user):
        """ 添加一个用户到昵称索引表 """
        if not self._nick_table.get(user.nick_name):
            self._nick_table[user.nick_name] = []
        self._nick_table[user.nick_name].append(user)

    def _load(self):
        """ 从文件加载数据 """
        self._user_info_table, self._info_file = \
            self._get_data(self._base_dir, self.INFO_DB_NAME, obj_hook=Storable.decode)
        self._user_pwd_table, self._pwd_file = \
            self._get_data(self._base_dir, self.PWD_DB_NAME)
        self._dist_id, self._dist_file = \
            self._get_data(self._base_dir, self.DIST_DB_NAME)
        self._changed = True
        # 缓存以昵称为索引表，加快用昵称查询的好友查找
        for user in self._user_info_table.values():
            self._add_user2nick_table(user)

    def __sync_backup_disk(self):
        """ 同步和备份数据 """
        pwd_path = os.path.join(self._base_dir, self.PWD_DB_NAME)
        pwd_bak_path = os.path.join(self._base_dir, self.PWD_DB_NAME+'.bak')
        info_path = os.path.join(self._base_dir, self.INFO_DB_NAME)
        info_bak_path = os.path.join(self._base_dir, self.INFO_DB_NAME+'.bak')
        dist_path = os.path.join(self._base_dir, self.DIST_DB_NAME)
        dist_bak_path = os.path.join(self._base_dir, self.DIST_DB_NAME+'.bak')

        self._disk_sync()
        self._l.acquire()
        shutil.copyfile(pwd_path, pwd_bak_path)
        shutil.copyfile(info_path, info_bak_path)
        shutil.copyfile(dist_path, dist_bak_path)
        self._l.release()

        self._timer = Timer(600, self.__sync_backup_disk)
        self._timer.start()

    @classmethod
    def _get_data(cls, base_dir, dbname, obj_hook=None):
        """ 从文件获取信息 """
        data, file = cls._load_db(base_dir, dbname, obj_hook=obj_hook)
        if not data:
            """ 新建的数据文件 """
            if dbname == cls.PWD_DB_NAME or dbname == cls.INFO_DB_NAME:
                data = {}
            elif dbname == cls.DIST_DB_NAME:
                data = 10000
        return data, file

    @staticmethod
    def _load_db(base_dir, dbname, obj_hook=None):
        """ 反序列化 """
        file, is_new = FileDatabase._open_file(base_dir, dbname)
        if is_new:
            return None, file
        try:
            data = json.load(file, object_hook=obj_hook)
            return data, file
        except json.JSONDecodeError as e:
            print(e)
            # 备份文件读取失败，抛出异常
            if dbname.endswith('bak'):
                raise IOError('DB read error, please fix it')
            # 如果读取主db文件失败，则读取备份文件
            data, _ = FileDatabase._load_db(base_dir, dbname+'.bak', obj_hook=obj_hook)
            return data, file

    @staticmethod
    def _open_file(base_dir, name):
        is_new = False
        path = os.path.join(base_dir, name)
        if not os.path.exists(path):
            file = open(path, 'w+')
            is_new = True
        else:
            file = open(path, 'r+')
        return file, is_new


class SQLDatabase(Database):
    """
        使用SQL数据库持久化
    """
    def __init__(self, sql_url):
        raise Exception('use FileDatabase')
