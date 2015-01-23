import telnetlib
import re
import datetime
import os

RN = '\r\n'
C_L = '\x0C'
C_Z = '\x1A'
ESC = '\x1B'
BS = '\x08'

class PTT():
    menu_header = r'【主功能表】.*批踢踢實業坊'
    board_footer = r'文章選讀.*回應.*推文.*轉錄.*相關主題.*找標題/作者.*進板畫面'
    post_footer = r'瀏覽.*第.*頁.*目前顯示.*第.*行.*回應.*推文.*離開'
    ansi_control = r'\x1b\[[0-9;]*[mABCDHJKsu]'

    def __init__(self):
        self.ptt = telnetlib.Telnet('ptt.cc')
        self.where = []

    def login(self, username, password, dup=False):
        if self.where:
            print('Already logged in')
            return

        self.__wait_til('註冊: ', encoding='big5')
        self.__send(username, ',', RN)
        self.__wait_til('密碼: ', encoding='big5')
        self.__send(password, RN)

        index = self.__expect('歡迎您再度拜訪', '請勿頻繁登入', '重複登入')[0]
        if index == 2:
            self.__send('n' if dup else 'y', RN)
            index = self.__expect('歡迎您再度拜訪', '請勿頻繁登入', timeout=10)[0]
        if index == 1:
            self.__send(RN)
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
        # skip board art
        self.__send('$$')
        try:
            index = self.__expect(PTT.board_footer)[0]
        except TimeoutError:
            raise Exception('No such board')

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

    def crawl_today(self, board=None):
        if board:
            self.to_board(board)
        if 'board' not in self.where[-1]:
            raise Exception('Not in any board')

        date = datetime.datetime.now()
        day, month, year = date.day, date.month, date.year
        # make dir YYYY_MM_DD/boardname
        dir_name = '_'.join([str(year), str(month), str(day)])
        dir_name = os.path.join(dir_name, self.where[-1].split('_')[-1])
        if not os.path.isdir(dir_name):
            os.makedirs(dir_name)

        self.__to_latest_post()
        while True:
            info = self.__entry_info()
            file_name = self.__gen_filename(info)
            file_name = os.path.join(dir_name, file_name)
            date = info['date'].strip().split('/')
            date = [int(x) for x in date]
            if date == [month, day]:
                if info['author'] != '-':
                    with open(file_name, 'w') as fp:
                        self.__download_post(fp)
                        print('Write to', file_name)
                    self.__send('qk', C_L)
                    self.where.pop()
                elif info['author'] == '-':
                    self.__send('k', C_L)
                self.__expect(PTT.board_footer)
            else:
                break

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

    def __expect(self, *args, encoding='utf-8', timeout=10):
        exp_list = [re.compile(exp.encode(encoding), re.MULTILINE) for exp in args]
        expect = self.ptt.expect(exp_list, timeout)
        if expect[0] == -1:
            raise TimeoutError(re.sub(PTT.ansi_control, '', expect[2].decode()))
        self.__flush()
        return expect

    def __download_post(self, fp=None):
        # go into post
        self.__send('l', C_L)
        self.where.append('article')
        index = self.__expect(PTT.post_footer, '此頁內容會依閱讀者不同')[0]
        if index == 1:
            return
        parser = re.compile(r'''
            (?P<percent>\d+)%   # the percentage of current view
            [^\d]*
            (?P<from_line>\d+)  # starting line number of current view
            ~
            (?P<to_line>\d+)    # ending line number of current view
            ''', re.VERBOSE | re.MULTILINE)

        from_line, to_line = 0, 0
        post = ''
        while True:
            self.__refresh()
            index, match, buf = self.__expect(PTT.post_footer, '此頁內容會依閱讀者不同')
            if index == 1:
                break
            footer = match.group(0)
            footer = self.__strip(footer.decode(), PTT.ansi_control)
            view = self.__strip(buf.decode(), PTT.ansi_control)

            progress = parser.search(footer).groupdict()
            if not progress:
                raise Exception('Post footer matching failed')
            progress = {key: int(progress[key]) for key in progress}
            n = 0
            # check overlapping
            if progress['from_line'] <= to_line:
                n = to_line - progress['from_line'] + 1
            view = '\n'.join(view.split('\n')[n:-1])
            post += view
            from_line, to_line = progress['from_line'], progress['to_line']

            if progress['percent'] == 100:
                break
            else:
                self.__send('\x06', C_L)
                self.__expect(PTT.post_footer)
        if fp:
            fp.write(post)
        else:
            print(post)

    def __to_latest_post(self):
        self.__refresh()
        self.__send('$$')
        self.__expect(PTT.board_footer)
        while True:
            info = self.__entry_info()
            # skip sticky post
            if '★' in info['number']:
                self.__send('k', C_L)
                self.__expect(PTT.board_footer)
            else:
                break

    def __entry_info(self):
        self.__refresh()
        view = self.__expect(PTT.board_footer)[2].decode()
        view = re.sub(PTT.ansi_control, '', view)
        view = re.sub(BS, '', view)
        parser = re.compile(r'''
            ●\s*                   # cursor and the following spaces
            (?P<number>\d+|★[ ]+?)   # post number or the star of sticky post
            [ ]                    # a whitespace
            (?P<status>.)          # status (read, unread, M, locked...)
            (?P<karma>[\d\sX]+|爆) # karma (XX, 1-99, 爆)
            (?P<date>../..)        # post date
            [ ]                    # a whitespace
            (?P<author>.*?)        # author name
            [ ]+                   # many whitespace
            ''', re.VERBOSE | re.MULTILINE)
        try:
            result = parser.search(view).groupdict()
        except:
            print(repr(view))
            raise Exception('Entry matching failed')
        else:
            return result

    def __gen_filename(self, info):
        if not info:
            raise Exception('Empty info')
        subber = re.compile(r'[/><|:&]')

        post_id = info['number'].strip()
        author = info['author'].strip()
        subber.sub('-', author)

        return '_'.join([post_id, author])

    def __strip(self, string, *args):
        for s in args:
            string = re.sub(s, '', string)
        while BS in string:
            string = re.sub('[\w\W]' + BS, '', string)
        return string

    class TimeoutError(Exception):
        pass

if __name__ == '__main__':
    pass
