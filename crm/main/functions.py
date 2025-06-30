from .models import Mahsulot, User, Pazanda, YetkazibBeruvchi
import datetime as dt
class new_yuklama:
    def __init__(self, mahsulot, miqdor,turi):
        self.nom = mahsulot
        self.miqdor = miqdor
        self.turi = turi


def mahsulotlar_miqdori(mahstr):
    from main.models import Mahsulot
    from collections import defaultdict

    if not mahstr:
        return []

    natija = {}  # nomi -> new_yuklama

    mahsulotlar = [item.strip() for item in mahstr.split(',') if item.strip()]
    
    for mahsulot in mahsulotlar:
        qismlar = mahsulot.rsplit(' ', 1)
        if len(qismlar) == 2:
            nomi, miqdor = qismlar
            nomi = nomi.strip()
            try:
                miqdor = int(miqdor.strip())
                mahsulot_obj = Mahsulot.objects.filter(nomi=nomi).first()
                turi = mahsulot_obj.turi if mahsulot_obj else "noma'lum"

                if nomi not in natija:
                    natija[nomi] = new_yuklama(nomi, miqdor, turi)
                else:
                    natija[nomi].miqdor += miqdor

            except ValueError:
                continue
    print(list(natija.values())[0].turi)
    return list(natija.values())
class addmahsulot:
    def __init__(self, mahsulot, miqdor,turi,xodim):
        self.nom = mahsulot
        self.miqdor = miqdor
        self.turi = turi
        self.xodim=xodim
    def __str__(self):
        return f"{self.xodim} {self.no,}ni {self.miqdor} qilib {self.turi} qo'shdi"
class addxodim:
    def __init__(self, xodim,user,turi):
        self.xodim = xodim
        self.user=user
        self.turi = turi
class user_newform(User):
    def get_newform(self):
        if self.type=='yetkazib_beruvchi':
            self.rasmi=YetkazibBeruvchi.objects.get(user=self).rasmi.url
        elif self.type=='pazanda':
            self.rasmi=Pazanda.objects.get(user=self).rasmi.url
    
        return self
def makenewform(User):
    res=[]
    for user in User:
        nuf=user_newform(user)
        res.append(nuf.get_newform)
    return res
def make_amal_log(amal):
    # mqoshish|mahsulot|miqdor|xodim mahsulot qoshish
    # myuklash|mahsulot|miqdor|yetkazuvchi mahsulot yuklash
    # msotish|mahsulot|miqdor|haridor mahsulot sotish
    # iqoshish|xodim|xturi|user xodim qoshish
    # imqoshish|xodim|mnomi|miqdor xodim qoshish
    amals=amal.split('|')
    turi=amals[0]
    
    if turi=='mqoshish':
        xodim=amals[3]
        mahsulot=amals[1]
        miqdor=amals[2]
        xturi='mahsulot qoshish'
    elif turi=='myuklash':
        mahsulot=amals[1]
        miqdor=amals[2]
        yetkazuvchi=amals[3]
        xturi='mahsulot yuklash'
    elif turi=='msotish':
        mahsulot=amals[1]
        miqdor=amals[2]
        haridor=amals[3]
        xturi='mahsulot sotish'
    elif turi=='iqoshish':
        xodim=amals[1]
        zturi=amals[2]
        xturi='xodim qoshish'
        user=amals[3]
    return turi