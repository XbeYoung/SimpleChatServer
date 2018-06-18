from utils import *
from msg_crypto import *
from user import Storable
import json


class Message(object):
    """
        所有消息基类
    """
    # 这里写这些属性是为了便于PyCharm好提示
    __slots__ = ['ID', 'cmd', 'msgid', 'pwd', 'success', 'user',
                 'nick_name', 'online', 'friend_id', 'reason', 'result', 'fuzzy',
                 'group', 'add', 'accept', 'allow_find', 'old_pwd',
                 'new_pwd', 'chat', 'exe_cmd']

    __TypeMap = {'cmd': int,            # 消息命令字
                 'msgid': int,          # 消息编号，暂时忽略
                 'exe_cmd': int,        # 返回客户端发来的cmd
                 'ID': str,             # 客户端ID/用户ID
                 'pwd': str,            # 用户密码
                 'friend_id': str,      # 好友ID
                 'nick_name': str,      # 昵称
                 'reason': str,         # 出错理由
                 'group': str,          # 添加/删除分组时的分组名称
                 'chat': str,           # 聊天消息'
                 'old_pwd': str,        # 旧密码
                 'new_pwd': str,        # 新密码
                 'fuzzy': bool,         # 模糊查找
                 'success': bool,       # 成功或失败
                 'online': bool,        # 在线或离线
                 'accept': bool,        # 同意或拒绝
                 'allow_find': bool,    # 允许或拒绝查找
                 'add': bool,           # 添加/删除
                 'result': dict,        # 返回查询结果字典
                 }

    DefaultMsg = []
    SpecialChar = {'\\': '[&124:]'}

    class Cmd(object):
        Login = 0
        Logout = 1
        Register = 2
        ReqUserInfo = 3
        Chat = 4
        AddDelFriend = 5
        AddDelGroup = 6
        AcceptDenyReq = 7
        QueryFriendInfo = 8
        FindFriend = 9
        SetInfo = 10
        ModifyPassword = 11
        RetFindResult = 95
        RetFriendInfo = 96
        RetOnlineNotify = 97
        RetUserInfo = 98
        Receipt = 99

    # 所有的类属性，实例属性，方法需在这里写一下, 不然拦截set/get方法后会提示找不到属性
    __InnerAttrs = ('_attrs', '_attrs_dict', '_keys',
                    'DefaultMsg', 'SpecialChar', 'Cmd',
                    '_check_dict', '_check_value',
                    'msg_crypto_bytes', 'msg', 'msg_json_bytes')

    def __new__(cls, *args, **kwargs):
        """
            __attrs 保存该消息格式中的字段
            _attrs 为子类的独有属性，通过子类的类属性设置，然后将其追加到__attrs实例属性中
        """
        obj = super().__new__(cls)
        obj._attrs = ['ID', 'cmd', 'msgid']
        obj._attrs.extend(obj._keys)
        return obj

    def __init__(self, attr_dict: dict):
        # print(attr_dict)
        """ 检测消息的长度和基本格式,然后将消息中的字段赋值给每个属性 """
        self._attrs_dict = attr_dict
        self._check_dict(attr_dict)

    def __setattr__(self, key, value):
        """ 拦截属性设置，直接修改字典中的值  """
        # print('set %s' % key)
        # 属性设置的时候通过父类方法设置，避免递归
        if key in Message.__InnerAttrs:
            # print(key, value)
            super().__setattr__(key, value)
        elif key in self._attrs:
            # 这里设置实际是先get到_attrs_dict ,然后对 _attrs_dict 的key设置值
            # 不是对_attrs_dict本身赋值，所以没有递归
            self._attrs_dict[key] = value
        else:
            raise AttributeError('%s no attribute %s' % (self.__class__, key))

    def __getattribute__(self, key):
        """ 返回属性值 """
        # print('get %s' % key)
        if key in Message.__InnerAttrs:
            return super().__getattribute__(key)
        elif key in super().__getattribute__('_attrs'):
            return super().__getattribute__('_attrs_dict')[key]
        else:
            raise AttributeError('%s no attribute %s' % (super().__getattribute__('__class__'), key))


    def _check_dict(self, attr_dict: dict):
        """ 检查消息字典与本类消息是否相符合 """
        if len(attr_dict) != len(self._attrs):
            print(attr_dict, self._attrs)
            raise Exception('msg type not match %d %d' % (len(attr_dict), len(self._attrs)))
        for attr in self._attrs:
            # 如果key不存在, 直接抛给上层处理
            v = attr_dict[attr]
            self._check_value(attr, v)

    def _check_value(self, k, v):
        if k == 'ID':
            if not v.isdigit():
                raise ValueError("ID error")

    @staticmethod
    def create_msg(msg: str):
        """ 消息类工厂方法 """
        try:
            msg = MsgCrypto.decrypto(msg)
            msg_dict = json.loads(msg)
        except json.JSONDecodeError as e:
            print(msg)
            print(e)
            raise ValueError('message format error')

        if len(msg_dict) < 3:  # 最短消息 ID cmd msgid
            raise ValueError('message format error')

        obj_map = {Message.Cmd.Login: LoginMsg,
                   Message.Cmd.Register: RegisterMsg,
                   Message.Cmd.Logout: LogoutMsg,
                   Message.Cmd.Chat: ChatMsg,
                   Message.Cmd.AddDelFriend: AddDelFriendMsg,
                   Message.Cmd.AddDelGroup: AddDelGroupMsg,
                   Message.Cmd.AcceptDenyReq: AcceptDenyReqMsg,
                   Message.Cmd.QueryFriendInfo: QueryFriendInfoMsg,
                   Message.Cmd.FindFriend: FindFriendMsg,
                   Message.Cmd.SetInfo: SetInfoMsg,
                   Message.Cmd.ModifyPassword: ModifyPasswordMsg,
                   Message.Cmd.ReqUserInfo: ReqUserInfoMsg
                   }

        if msg_dict['cmd'] not in obj_map:
            raise ValueError('message command error')
        return obj_map[msg_dict['cmd']](msg_dict)

    @property
    def msg(self):
        return str(self._attrs_dict)

    @property
    def msg_crypto_bytes(self):
        s = json.dumps(self._attrs_dict, default=Storable.encode)
        # print(MsgCrypto.encrypto(s).encode('utf-8').decode('utf-8'))
        return MsgCrypto.encrypto(s).encode('utf-8')

    @property
    def msg_json_bytes(self):
        return json.dumps(self._attrs_dict, default=Storable.encode).encode('utf-8')


''' -------------------------------请求消息----------------------------------- '''


class LoginMsg(Message):
    _keys = ['pwd']
    DefaultMsg = {"ID": "0",
                  "cmd": Message.Cmd.Login,
                  "msgid": 0,
                  "pwd": ""}


class LogoutMsg(Message):
    _keys = []
    DefaultMsg = {"ID": "0",
                  "cmd": Message.Cmd.Logout,
                  "msgid": 0
                  }


class RegisterMsg(Message):
    _keys = ['pwd', 'nick_name']
    DefaultMsg = {"ID": "0",
                  "cmd": Message.Cmd.Register,
                  "msgid": 0,
                  "pwd": "",
                  "nick_name": ""
                  }


class ReqUserInfoMsg(Message):
    _keys = []
    DefaultMsg = {"ID": "0",
                  "cmd": Message.Cmd.ReqUserInfo,
                  "msgid": 0
                  }


class ChatMsg(Message):
    _keys = ['chat', 'friend_id', 'nick_name']
    DefaultMsg = {"ID": "0",
                  "cmd": Message.Cmd.Chat,
                  "msgid": 0,
                  "chat": "",
                  "friend_id": "0",
                  "nick_name": ""
                  }


class AddDelFriendMsg(Message):
    _keys = ['friend_id', 'nick_name', 'group', 'add']
    DefaultMsg = {"ID": "0",
                  "cmd": Message.Cmd.AddDelFriend,
                  "msgid": 0,
                  "friend_id": "0",
                  "nick_name": "",
                  "group": "friends",
                  "add": True
                  }


class AddDelGroupMsg(Message):
    _keys = ['group', 'moveto', 'add']
    DefaultMsg = {"ID": "0",
                  "cmd": Message.Cmd.AddDelGroup,
                  "msgid": 0,
                  "group": "",
                  "moveto": "",
                  "add": True
                  }


class AcceptDenyReqMsg(Message):
    _keys = ['group', 'friend_id', 'nick_name', 'accept']
    DefaultMsg = {"ID": "0",
                  "cmd": Message.Cmd.AcceptDenyReq,
                  "msgid": 0,
                  "group": "friends",
                  "nick_name": "",
                  "friend_id": "0",
                  "accept": True
                  }


class QueryFriendInfoMsg(Message):
    _keys = ['friend_id']
    DefaultMsg = {"ID": "0",
                  "cmd": Message.Cmd.QueryFriendInfo,
                  "msgid": 0,
                  "friend_id": "0"
                  }


class FindFriendMsg(Message):
    _keys = ['friend_id', 'nick_name', 'fuzzy']
    DefaultMsg = {"ID": "0",
                  "cmd": Message.Cmd.FindFriend,
                  "msgid": 0,
                  "friend_id": "0",
                  "nick_name": "",
                  "fuzzy": False
                  }


class SetInfoMsg(Message):
    _keys = ['nick_name', 'sex', 'allow_find',
             'birthday', 'desc', 'ext_info']
    DefaultMsg = {"ID": "0",
                  "cmd": Message.Cmd.SetInfo,
                  "msgid": 0,
                  "nick_name": "",
                  "sex": "M",
                  "allow_find": True,
                  "birthday": "2018-01-01",
                  "desc": "",
                  "ext_info": {}
                  }


class ModifyPasswordMsg(Message):
    _keys = ['old_pwd', 'new_pwd']
    DefaultMsg = {"ID": "0",
                  "cmd": Message.Cmd.ModifyPassword,
                  "msgid": 0,
                  "old_pwd": "",
                  "new_pwd": ""
                  }


''' -------------------------------响应消息----------------------------------- '''


class RetUserInfoMsg(Message):
    """ 用户信息响应 """
    _keys = ['success', 'user', 'reason', 'exe_cmd']
    DefaultMsg = {'ID': '0',
                  'cmd': Message.Cmd.RetUserInfo,
                  'msgid': 0,
                  'exe_cmd': 0,
                  'success': False,
                  'reason': 'id or password error',
                  'user': {}
                  }


class RetOnlineNotifyMsg(Message):
    """ 通知好友上下线消息 """
    _keys = ['friend_id', 'nick_name', 'online']
    DefaultMsg = {'ID': '0',
                  'cmd': Message.Cmd.RetOnlineNotify,
                  'msgid': 0,
                  'friend_id': None,
                  'nick_name': None,
                  'online': False}


class RetFriendInfoMsg(Message):
    _keys = ['group', 'result']
    DefaultMsg = {'ID': '0',
                  'cmd': Message.Cmd.RetFriendInfo,
                  'msgid': 0,
                  'group': None,
                  'result': None}


class RetFindResultMsg(Message):
    _keys = ['result']
    DefaultMsg = {'ID': '0',
                  'cmd': Message.Cmd.RetFindResult,
                  'msgid': 0,
                  'result': None}



class ReceiptMsg(Message):
    """ 回执消息响应 """
    _keys = ['reason', 'success', 'exe_cmd']
    DefaultMsg = {'ID': '0',
                  'cmd': Message.Cmd.Receipt,
                  'msgid': 0,
                  'exe_cmd': 0,
                  'success': False,
                  'reason': 'message format error'}



