import random
from poem_reciter.repository import normalize_poem_text

class PoemReciter:
    
    def loadPoems(self):
        #print("Load Poems")
        #self.poems = {'闻王昌龄左迁龙标遥有此寄 【唐】李白':'杨花落尽子规啼\n闻道龙标过五溪\n我寄愁心与明月\n随君直到夜郎西'}
        self.poems = {}
        with open("Poems", 'r', encoding='utf-8') as f:
            for line in f.readlines():
                line = line.strip()
                poemName, poemText = line.split("：")
                self.poems[poemName.strip()] = normalize_poem_text(poemText.replace("\\n", "\n"))
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
        answer = normalize_poem_text('\n'.join(iter(input, sentinel)))
        if (self.poemText == answer):
            print("正确！")
        else:
            print("错误！ 正确的原诗文本是：")
            print(self.poemText + "\n")
            print("而您输入的是：")
            print(answer + "\n")

if __name__ == "__main__":
    pr = PoemReciter()
    while(1):
        pr.loadPoems()
        pr.recite()
        if ('y' != input("是否继续[Y/y]：").casefold()):
            break
