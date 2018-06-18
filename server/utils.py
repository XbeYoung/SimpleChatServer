import re
from functools import wraps

__all__ = ['Check', 'use_log']


def use_log(func):
    @wraps(func)
    def inner(*args, **kwargs):
        print('+++++++++++%s+++++++++++++' % func.__name__)
        ret = func(*args, **kwargs)
        print('-----------%s-------------' % func.__name__)
        return ret
    return inner


class Check(object):
    """
        数据合法性检查工具类
    """
    _pwd_pattern = re.compile('[a-z0-9*&@_.]{8}', re.I)
    _name_pattern = re.compile('.*[,\*\.:\(\)|<>/\\\\].*', re.I)
    _date_pattern = re.compile("^(?:(?!0000)[0-9]{4}-(?:(?:0[1-9]|1[0-2])-"
                               "(?:0[1-9]|1[0-9]|2[0-8])|(?:0[13-9]|1[0-2])"
                               "-(?:29|30)|(?:0[13578]|1[02])-31)|"
                               "(?:[0-9]{2}(?:0[48]|[2468][048]|[13579][26])|"
                               "(?:0[48]|[2468][048]|[13579][26])00)-02-29)$")

    @staticmethod
    def check_pwd(pwd: str):
        return bool(Check._pwd_pattern.match(pwd))

    @staticmethod
    def check_name(name: str):
        return not bool(Check._name_pattern.match(name))

    @staticmethod
    def check_date(date: str):
        return bool(Check._date_pattern.match(date))

    @staticmethod
    def check_sex(sex: str):
        return sex == 'B' or sex == 'G'

    @staticmethod
    def check_url(url: str):
        pass
        return True
