import telnetlib
import re

RN = '\r\n'
C_L = '\x0C'
C_Z = '\x1A'
ESC = '\x1B'

class PTT():
    menu_header = r'【主功能表】.*批踢踢實業坊'
    board_footer = r'文章選讀.*回應.*推文.*轉錄.*相關主題.*找標題/作者.*進板畫面'
    ansi_control = r'\x1b\[[0-9;]*[mABCDHJKsu]'

    def __init__(self):
        self.ptt = telnetlib.Telnet('ptt.cc')
        self.where = []

    def login(self, username, password, dup=False):
        if self.where:
            return

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
        self.__send(RN)

        # check if there's login attempt log
        index = self.__expect(PTT.menu_header, '錯誤嘗試')[0]
        if index == 1:
            # don't delete the log
            self.__send('n', RN)
        # in menu now
        self.where.append('menu')

    def to_board(self, board):
        self.to_menu()
        self.__send('s', board, RN)
        try:
            index = self.__expect(PTT.board_footer, '任意鍵')[0]
            if index == 1:
                self.__send(RN)
        except TimeoutError:
            print('No such board')
            return
        self.__expect(PTT.board_footer)
        # in board now
        # get the board name
        self.__refresh()
        name = self.__expect(r'看板《(.*)》')[1].group(1).decode()
        self.where.append('board_' + name)

    def to_menu(self):
        while self.where[-1] != 'menu':
            self.__send('q')
            self.where.pop()
        self.__refresh()
        self.__expect(PTT.menu_header)

    def close(self):
        self.ptt.close()
        print('Connection closed')

    def __flush(self):
        return self.ptt.read_very_eager()

    def __refresh(self):
        self.__flush()
        self.__send(C_L)

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
