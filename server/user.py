class Storable(object):

    def __init__(self, **kwargs):
        """ 使用字典反序列化 """
        self.__set_attrs(kwargs)

    def __set_attrs(self, attr_dict: dict):
        for attr in self.__slots__:
            v = attr_dict.get(attr)
            self.__setattr__(attr, v)

    def __encode__(self):
        """ 序列化 """
        d = self.__pack_attrs(self.__exclude_storage__)
        d['class'] = self.__class__.__name__
        return d

    def __str__(self):
        d = self.__pack_attrs(self.__exclude_str__)
        return str(d)

    def __dict__(self):
        return self.__pack_attrs(self.__exclude_dict__)

    def __pack_attrs(self, exclude_func):
        """ 将属性包装成字典, exclude_func为排除方法 """
        exclude = exclude_func()
        include = set(exclude) ^ set(self.__slots__)
        d = {}
        for attr in include:
            d[attr] = self.__getattribute__(attr)
        return d

    @staticmethod
    def __exclude_storage__() -> tuple:
        """ 子类有些属性不需要序列化，通过该方法排除香关属性 """
        return tuple()

    @staticmethod
    def __exclude_dict__():
        return tuple()

    @staticmethod
    def __exclude_str__() -> tuple:
        """ 子类有些属性不需要被输出显示，通过该方法排除相关属性 """
        return tuple()

    @staticmethod
    def encode(obj):
        """ json序列化方法 """
        # print('------JSON-----------%s' % obj)
        if isinstance(obj, Storable):
            return obj.__encode__()
        return obj

    @staticmethod
    def decode(obj):
        """ json反序列化方法，Storable类再序列化的时候会将 class 名字存储起来 """
        """ 反序列化时，通过eval动态创建对象 """
        if 'class' in obj:
            cls = obj['class']+'(**obj)'
            return eval(cls)
        return obj


class User(Storable):
    """
        可序列化用户对象, 对应字典格式如下
        {
            "ID": "111111",
            "nick_name": "haha",
            "sex": "B/G",
            "birthday": "2000-01-01",
            "desc": "ITer",
            "allow_find": true,
            "online": true,
            "groups": {
                        "friends": ["xxxx", "xxxxx"]
                        "classmate":["xxxxxx", "xxxxx"]
                        ....
                        }
            "ext_info": {"扩展字段,暂时无效"}
        }
    """
    __slots__ = ['ID', 'nick_name', 'sex', 'birthday',
                 'desc', 'allow_find', 'online', 'groups',
                 'ext_info']

    __DefaultGroup = 'friends'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.groups:
            self.groups = {self.__DefaultGroup: []}
        self.online = False

    def has_friend(self, ID: str) -> (bool, str):
        """ 查找好友 """
        for group, friend_set in self.groups.values():
            if ID in friend_set:
                return True, group
        return False, None

    def add_friend2group(self, friend_id, group: str) -> bool:
        """ 添加一个好友到分组 """
        if self.has_friend(friend_id)[0]:
            # 找到好友直接返回
            return False
        # 没找到，向group中里面添加一个好友
        self.add_group(group)
        self.groups[group].append(friend_id)
        return True

    def del_friend4group(self, friend_id) -> bool:
        """ 从一个分组删除一个好友 """
        has_friend, group = self.has_friend(friend_id)
        if has_friend:
            self.groups[group].remove(friend_id)
            return True
        return False

    def move_friend2group(self, friend, old_g, new_g):
        if old_g == new_g:
            return False
        if friend not in self.groups[old_g]:
            return False
        if self.groups.get(new_g):
            return False
        self.groups[old_g].remove(friend)
        self.groups[new_g].append(friend)

    def add_group(self, group: str) -> bool:
        """ 添加一个分组 """
        if not self.groups.get(group):
            self.groups[group] = []
            return True
        return False

    def del_group(self, group: str, new_group: str='friends') -> bool:
        """ 删除一个分组 """
        if group == self.__DefaultGroup or not self.groups.get(group):
            return False
        if not self.groups.get(new_group):
            return False
        # 将原分组的好友移动到新分组
        self.groups[new_group].extend(self.groups[group])
        del self.groups[group]
        return True

    def simple_info(self):
        return {'ID': self.ID,
                'online': self.online,
                'nick_name': self.nick_name}

    def public_info(self):
        return {'ID': self.ID,
                'online': self.online,
                'nick_name': self.nick_name,
                'sex': self.sex,
                'birthday': self.birthday,
                'desc': self.desc,
                'ext_info': self.ext_info}

    @staticmethod
    def __exclude_storage__() -> tuple:
        return ('online',)

    def __eq__(self, other):
        return self.ID == other.ID

