import telnetlib
import re

RN = '\r\n'
C_L = '\x0C'
C_Z = '\x1A'
ESC = '\x1B'

class PTT():
    def __init__(self):
        self.ptt = telnetlib.Telnet('ptt.cc')
        self.where = 'login'

    def login(self, username, password, dup=False):
        self.__wait_til('註冊: ', encoding='big5')
        self.__send(username, ',', RN)
        self.__wait_til('密碼: ', encoding='big5')
        self.__send(password, RN)

        index = self.__expect('歡迎您再度拜訪', '重複登入', '請勿頻繁登入')[0]
        if index == 2:
            self.__send(RN)
            index = self.__expect('歡迎您再度拜訪', '重複登入')[0]
        if index == 1:
            self.__send('n' if dup else 'y', RN)
            index = self.__expect('歡迎您再度拜訪')[0]
        if index == -1:
            print("Login failed")
            self.close()
        self.__send(RN)

        index = self.__expect('【主功能表】', '錯誤嘗試')[0]
        if index == 1:
            self.__send('y', RN)
        # in menu now
        self.where = 'menu'

    def close(self):
        self.ptt.close()
        print('Connection closed')

    def __wait_til(self, exp, encoding='utf-8', timeout=None):
        return self.ptt.read_until(exp.encode(encoding), timeout)

    def __send(self, *args):
        s = ''.join(args)
        self.ptt.write(s.encode())

    def __expect(self, *args, encoding='utf-8', timeout=5):
        exp_list = [exp.encode(encoding) for exp in args]
        expect = self.ptt.expect(exp_list, timeout)
        if expect[0] == -1:
            raise TimeoutError(expect[2])
        return expect

    class TimeoutError(Exception):
        pass

if __name__ == '__main__':
    pass
