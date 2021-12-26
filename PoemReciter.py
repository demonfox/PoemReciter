import random

class PoemReciter:
    
    def loadPoems(self):
        #print("Load Poems")
        #self.poems = {'闻王昌龄左迁龙标遥有此寄 【唐】李白':'杨花落尽子规啼\n闻道龙标过五溪\n我寄愁心与明月\n随君直到夜郎西'}
        self.poems = {}
        with open("Poems", 'r') as f:
            for line in f.readlines():
                line = line.strip()
                poemName, poemText = line.split("：")
                self.poems[poemName] = poemText.replace("\\n", "\n")
        self.pickRandomPoem()
    
    def pickRandomPoem(self):
        #print("Pick Random Poem")
        self.poemName, self.poemText = random.choice(list(self.poems.items()))
    
    def printCurrentPoem(self):
        print(self.poemName)
        print(self.poemText)

    def recite(self):
        self.pickRandomPoem()
        print("请背诵：{poemName}".format(poemName = self.poemName))
        #print(self.poemText)
        sentinel = ''
        answer = '\n'.join(iter(input, sentinel))
        if (self.poemText == answer):
            print("正确！")
        else:
            print("错误！ 正确的原诗文本是：")
            print(self.poemText + "\n")
            print("而您输入的是：")
            print(answer + "\n")

pr = PoemReciter()
while(1):
    pr.loadPoems()
    pr.recite()
    if ('y' != input("是否继续[Y/y]：").casefold()):
        break
