from message import *
from database import Database
from global_manager import GlobalManger
from utils import *
from user import User
import socket
import traceback
import threading


class Transfer(threading.Thread):
    """
        数据交互类
        维持客户端与服务器的数据交互和客户端的消息转发
    """
    def __init__(self, sock: socket.socket, name=None):
        super().__init__(name=name)
        self._func_map = {Message.Cmd.Logout: self._logout_msg,
                          Message.Cmd.Chat: self._chat_msg,
                          Message.Cmd.AddDelFriend: self._add_del_friend_msg,
                          Message.Cmd.AddDelGroup: self._add_del_group_msg,
                          Message.Cmd.AcceptDenyReq: self._accept_friend_msg,
                          Message.Cmd.QueryFriendInfo: self._get_friend_info_msg,
                          Message.Cmd.FindFriend: self._find_friend_msg,
                          Message.Cmd.SetInfo: self._set_user_info_msg,
                          Message.Cmd.ModifyPassword: self._modify_password_msg,
                          Message.Cmd.ReqUserInfo: self._req_user_info_msg}

        self._sock = sock
        self._peer = self._sock.getpeername()
        self._user = None
        self._req_friend_msg = []
        self._global_info = GlobalManger()
        self._db = Database.create_db()
        self._be_quit = False

    def run(self):
        """ 主循环 """
        retry = 100
        while not self._be_quit:
            try:
                data = self._sock.recv(4096)
            except Exception as e:
                print(e)
                break

            if not data:
                break

            try:
                msg = Message.create_msg(data.decode('utf-8'))
            except Exception as e:
                print(traceback.format_exc())
                self._send_receipt(0, False, str(e))
                if --retry == 0:
                    self.ready2exit()
                continue
            # print('%s recv : %s' % (threading.current_thread(), msg.msg))
            # 没有登陆使用未登录的函数处理消息
            if not self._user:
                self.__nologin_process(msg)
            else:
                self.__has_logged_process(msg)

        # 将自己从全局信息类中删除，再断开socket连接
        # 防止先断开连接的时候，其他进程调用本类的send方法发送数据
        if self._user:
            self._global_info.del_connect(self._user.ID)
        self._sock.close()
        print('%s----exit' % self.name)

    @use_log
    def _login_process(self, msg):
        """ 处理用户登陆 """
        assert type(msg) == LoginMsg

        # 判断用户是否已经登陆
        if self._global_info.is_login(msg.ID):
            self._send_user_info(msg.cmd, False, '用户已经登陆')
            self.ready2exit()
        else:
            # 判断用户名和密码
            if self._db.check_user_pwd(msg.ID, msg.pwd):
                print(msg.ID, '登陆成功')
                self._user = self._db.query_user(msg.ID)
                self._global_info.add_connect(msg.ID, self)
                self._user.online = True
                self._notify_friend(True)
                self._send_user_info(msg.cmd)
                # 将线程名改为 "用户:ID"
                self.name = "用户:" + self._user.ID
            else:
                self._send_user_info(msg.cmd, False, 'id未注册或密码错误')
                print(msg.ID, msg.pwd, '登陆失败')

    @use_log
    def _register_process(self, msg):
        """ 处理用户注册 """
        assert type(msg) == RegisterMsg

        print(msg.nick_name, '注册成功')
        # 分配ID, 存储用户, 返回消息
        ID = self._db.distribution_id()
        user = User(ID=ID, nick_name=msg.nick_name)
        self._db.add_user(user, msg.pwd)
        self._send_receipt(msg.cmd, ID=ID)
        # print(user)

    @use_log
    def _logout_msg(self, **kwargs):
        """ 注销处理 """
        msg = kwargs.get('msg')
        assert type(msg) == LogoutMsg

        self._send_receipt(msg.cmd)
        self._user.online = False
        self._notify_friend(False)
        self.ready2exit()

    @use_log
    def _chat_msg(self, **kwargs):
        """ 聊天消息转发 """
        msg = kwargs.get('msg')
        assert type(msg) == ChatMsg

        # 将消息转发给toID的用户
        toID = msg.friend_id
        msg.friend_id = self._user.ID
        msg.nick_name = self._user.nick_name
        if toID == self._user.ID:
            self._send_receipt(msg.cmd, False, '不能发送消息给自己')
        elif self._user.has_friend(toID)[0]:
            self._global_info.send_msg2id(toID, msg)
            self._send_receipt(msg.cmd)
        else:
            self._send_receipt(msg.cmd, False, str('%s 不是您的朋友' % toID))

    @use_log
    def _add_del_friend_msg(self, **kwargs):
        """ 添加或删除好友 """
        msg = kwargs.get('msg')
        assert type(msg) == AddDelFriendMsg
        if msg.add:
            fid = msg.friend_id
            # id 不能为自己 且 在DB中找到用户
            if fid != self._user.ID and self._db.query_user(msg.friend_id):
                # 保存要添加的好友的消息
                self._save_req_friend_msg(msg)
                # 转发添加好友的消息，将ID和昵称换成自己的
                # 这里需要创建新的对象，否则改掉id后会影响保存的消息数据
                trans_msg = AddDelFriendMsg(AddDelFriendMsg.DefaultMsg)
                trans_msg.friend_id = self._user.ID
                trans_msg.nick_name = self._user.nick_name
                trans_msg.group = None
                self._global_info.send_msg2id(fid, trans_msg)
                self._send_receipt(msg.cmd, True, 'success')
            else:  # 在DB中未找到用户
                self._send_receipt(msg.cmd, False, '没有找到id为 %s 的用户', fid)
        else:  # 删除好友
            if self._user.del_friend4group(msg.friend_id, msg.group):
                self._db.data_changed()
                self._send_receipt(msg.cmd)
            else:
                self._send_receipt(msg.cmd, False, '好友或分组不存在')

    @use_log
    def _accept_friend_msg(self, **kwargs):
        """ 同意或拒绝好友添加 """
        msg = kwargs.get('msg')
        assert type(msg) == AcceptDenyReqMsg

        if msg.accept:
            # 查找同意的ID是否在请求列表中
            req_msg = self._find_save_req_msg(msg)
            if not req_msg:
                self._send_receipt(msg.cmd, False, str('%s 的用户没有添加您或消息已过期' % msg.friend_id))
                return
            # 在_req_friend_ids中的id一定是能被查询到的,在_add_del_friend中已经做过检查
            self._user.add_friend2group(msg.friend_id, msg.group)
            self._send_receipt(msg.cmd)
            self._remove_req_msg(msg)

        # 如果拒绝添加，直接转发
        msg.group = None
        fid = msg.friend_id
        msg.friend_id = self._user.ID
        msg.nick_name = self._user.nick_name
        self._global_info.send_msg2id(fid, msg)

    @use_log
    def _get_friend_info_msg(self, **kwargs):
        """ 获取好友信息 """
        msg = kwargs.get('msg')
        assert type(msg) == QueryFriendInfoMsg
        if not self._user.find_friend(msg.friend_id):
            self._send_receipt(msg.cmd, False, str('not found friend %d' % msg.friend_id))
            return
        # 获取好友信息，返回好友信息
        ret_msg = RetFriendInfoMsg(RetFriendInfoMsg.DefaultMsg)
        ret_msg.result = self._user.public_info()
        self.send(ret_msg)

    @use_log
    def _find_friend_msg(self, **kwargs):
        """ 查找朋友 """
        msg = kwargs.get('msg')
        assert type(msg) == FindFriendMsg

        ret_msg = RetFindResultMsg(RetFindResultMsg.DefaultMsg)
        ret_msg.result = []
        users = []  # 防止id和nick都为None时出现users没定义的异常
        if msg.friend_id:
            # 按ID查询
            users = self._db.find_user4id(msg.friend_id, msg.fuzzy)
        elif msg.nick_name:
            # 按昵称查询
            users = self._db.find_user4nickname(msg.nick_name, msg.fuzzy)

        for user in users:
            if user.allow_find:  # 用户允许被查找则添加到结果中
                ret_msg.result.append(user.simple_info())
        self.send(ret_msg)

    @use_log
    def _set_user_info_msg(self, **kwargs):
        """ 设置个人信息 """
        msg = kwargs.get('msg')
        assert type(msg) == SetInfoMsg

        self._user.nick_name = msg.nick_name
        self._user.sex = msg.sex
        self._user.birthday = msg.birthday
        self._user.desc = msg.desc
        self._user.ext_info = msg.ext_info
        self._user.allow_find = msg.allow_find

        self._send_receipt(msg.cmd, True, 'success')
        self._db.data_changed()

    @use_log
    def _modify_password_msg(self, **kwargs):
        """ 修改密码 """
        msg = kwargs.get('msg')
        assert type(msg) == ModifyPasswordMsg
        if self._db.modify_pwd(self._user.ID, msg.old_pwd, msg.new_pwd):
            self._send_receipt(msg.cmd)
        else:
            self._send_receipt(msg.cmd, False, 'password error')

    @use_log
    def _add_del_group_msg(self, **kwargs):
        """ 添加或删除分组 """
        msg = kwargs.get('msg')
        assert type(msg) == AddDelGroupMsg

        reason = None
        if msg.add:
            if not self._user.add_group(msg.group):
                reason = '分组已存在'
        else:
            if not self._user.del_group(msg.group, msg.moveto):
                reason = '分组不存在'
        if reason:
            self._send_receipt(msg.cmd, False, reason)
        else:
            self._db.data_changed()
            self._send_receipt(msg.cmd)

    @use_log
    def _req_user_info_msg(self, **kwargs):
        msg = kwargs.get('msg')
        assert type(msg) == ReqUserInfoMsg
        self._send_user_info(msg.cmd)

    def _notify_friend(self, online: bool):
        """ 通知好友上线/通知好友下线 """
        msg = RetOnlineNotifyMsg(RetOnlineNotifyMsg.DefaultMsg)
        # 此处是自己的ID，告诉朋友自己上线了
        msg.friend_id = self._user.ID
        msg.nick_name = self._user.nick_name
        msg.online = online

        # 遍历好友列表，逐个通知好友
        for flist in self._user.groups.values():
            for friend_id in flist:
                self._global_info.send_msg2id(friend_id, msg)

    def __nologin_process(self, msg: Message) -> bool:
        """ 用户未登陆时的消息处理 """
        if msg.cmd == Message.Cmd.Login:
            self._login_process(msg)
        elif msg.cmd == Message.Cmd.Register:
            self._register_process(msg)
        else:
            self._send_receipt(msg.cmd, False, '请登录后操作')
            return False
        return True

    def __has_logged_process(self, msg: Message) -> bool:
        """ 用户登陆后的消息处理 """
        ret = False
        func = self._func_map.get(msg.cmd)
        if not func:
            self._send_receipt(msg.cmd, False, '命令错误')
        else:
            try:
                func(msg=msg)
                ret = True
            except AssertionError:
                # 断言错误, 一般不可能产生这种错误, 因为消息是按照命令来解析的
                print(traceback.format_exc())
                self.ready2exit()
                self._send_receipt(msg.cmd, False, 'message format error')
            except Exception as e:
                print(traceback.format_exc())
                self._send_receipt(msg.cmd, False, str(e))
        return ret

    def _send_user_info(self, execmd, succ=True, reason='success'):
        """ 发送用户信息 """
        msg = RetUserInfoMsg(RetUserInfoMsg.DefaultMsg)
        msg.exe_cmd = execmd
        msg.success = succ
        msg.reason = reason
        if succ:
            msg.user = self._user.__dict__()
            for key, group in self._user.groups.items():
                for friend_id in group:
                    friend = self._db.query_user(friend_id)
                    if friend:
                        msg.user['groups'][key] = friend.simple_info()
        else:
            msg.user = {}
        self.send(msg)

    def _send_receipt(self, exec_cmd, succ=True, reason='success', ID='0'):
        """ 发送消息回执 """
        msg = ReceiptMsg(ReceiptMsg.DefaultMsg)
        msg.success = succ
        msg.reason = reason
        msg.exe_cmd = exec_cmd
        msg.ID = ID
        self.send(msg)

    def _save_req_friend_msg(self, msg: Message):
        """ 将请求加好友的ID存储起来 """
        self._req_friend_msg.append(msg)
        # 最多保存100个请求
        if len(self._req_friend_msg) > 50:
            del self._req_friend_msg[0]

    def _find_save_req_msg(self, msg: Message):
        for m in self._req_friend_msg:
            if m.friend_id == msg.friend_id:
                return m
        return None

    def _remove_req_msg(self, msg: Message):
        reserved_msg = []
        # 可能有多个相同的好友请求,所以需要全部遍历
        for m in self._req_friend_msg:
            if m.friend_id != msg.friend_id:
                reserved_msg.append(m)
        self._req_friend_msg = reserved_msg


    def ready2exit(self):
        """ 准备退出 """
        self._be_quit = True
        self._sock.shutdown(socket.SHUT_RD)

    def send(self, msg: Message):
        """ 消息发送函数 """
        self._sock.send(msg.msg_crypto_bytes)

    def recv_notify(self, msg: Message) -> bool:
        """ 接受其他用户发来的消息 """

        # 请求添加好友的消息
        if type(msg) == AddDelFriendMsg:
            # 保存请求添加好友的ID,在将消息转发给自己的客户端
            self._save_req_friend_msg(msg)
            self.send(msg)
            return True

        # 好友同意或拒绝添加自己
        if type(msg) == AcceptDenyReqMsg:
            if msg.accept:
                # 由于只有自己的请求中才含有分组信息，所以需要将自己发送的请求消息拿出来
                req_msg = self._find_save_req_msg(msg)
                self._user.add_friend2group(msg.friend_id, req_msg.group)
            self._remove_req_msg(msg)
            self.send(msg)

        if type(msg) == RetOnlineNotifyMsg:
            self.send(msg)
            return True

        if type(msg) == ChatMsg:
            self.send(msg)
            return True

    def ID(self):
        return self.name