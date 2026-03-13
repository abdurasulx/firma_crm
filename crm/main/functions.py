from .models import Mahsulot, User, Pazanda, YetkazibBeruvchi
import datetime as dt
class new_yuklama:
    def __init__(self, mahsulot, miqdor,turi,narx):
        self.nom = mahsulot
        self.miqdor = miqdor
        self.turi = turi
        self.narx=narx


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
                
                if not mahsulot_obj:
                    # Skip products that no longer exist in the system
                    continue

                turi = mahsulot_obj.turi
                narx = mahsulot_obj.narxi

                if nomi not in natija:
                    natija[nomi] = new_yuklama(nomi, miqdor, turi, narx)
                else:
                    natija[nomi].miqdor += miqdor

            except ValueError:
                continue
    
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
def yuklama_maker(mahsulotlar):
    res = ''
    for i in mahsulotlar:
        nom = i.nom
        miqdor = i.miqdor
    
        res += f"{nom} {miqdor},"
    return res
def accptyuk(user,yuk):
    yt=YetkazibBeruvchi.objects.get(user=user)
    
    
    

    
    
    mxs=Mahsulot.objects.get(nomi=yuk.mahsulot.nomi)
    if mxs.miqdori>=yuk.miqdor:
        
        yt.mahsulotlar+=f'{yuk.mahsulot} {int(yuk.miqdor)},'
        yuk.mode='done'
        yuk.tasdiq=True
        yuk.save()
        mxs.miqdori-=int(yuk.miqdor)
        mxs.save()
    else:
        yuk.mode='rejected'
        yuk.tasdiq=True
        yuk.save()
    yt.save()
    
def sotishm(mahs,yt):
    ytyk=yt.mahsulotlar
    ytyk=ytyk.split(',')
    natija={}
    for y in ytyk:
        if y.strip():
            y_parts = y.strip().rsplit(' ', 1)
            if len(y_parts) == 2:
                natija[y_parts[0].strip()] = int(y_parts[1].strip())
    
    mahs_list = mahs.split(',')
    
    for m in mahs_list:
        if m.strip():
            n = m.strip().rsplit(' ', 2) # Name Quantity Price
            if len(n) >= 2:
                prod_nom = n[0].strip()
                prod_qty = int(float(n[1].strip()))
                if prod_nom in natija:
                    natija[prod_nom] -= prod_qty
    sotl=''
    for i in natija:
        if natija[i] > 0:
            # Clean up missing products: only keep if product still exists in Mahsulot table
            if Mahsulot.objects.filter(nomi=i).exists():
                sotl += f'{i} {natija[i]},'


    yt.mahsulotlar=sotl
    yt.save()
class sotuv_new_form:
    def __init__(self,mahsulot,savdo):
        self.nomi=mahsulot[0]
        self.miqdori=mahsulot[1]
        self.narxi=mahsulot[2]
        self.haridor_dukon=savdo.haridor_dukon
        self.yetkazib_beruvchi=savdo.yetkazib_beruvchi
        self.oluvchining_ismi=savdo.oluvchining_ismi
        self.st=savdo.st
        self.tulandi=savdo.tulandi
        self.tasdiq_kutilmoqda=savdo.tasdiq_kutilmoqda
        self.summa=savdo.summa
        self.smm=savdo.smm
        print(savdo.smm)
        self.smr=savdo.smr.url
        self.vaqt_sana=savdo.vaqt_sana

    #     haridor_dukon = models.ForeignKey(HaridorDukon, on_delete=models.CASCADE)
    # yetkazib_beruvchi = models.ForeignKey(YetkazibBeruvchi, on_delete=models.CASCADE)
    # vaqt_sana = models.DateTimeField(auto_now_add=True)
    # oluvchining_ismi = models.CharField(max_length=255)
    # smm = models.TextField(verbose_name="Sotilgan mahsulot miqdori", blank=True, null=True)
    # smr = models.ImageField(upload_to='savdo/')
    # st = models.CharField(max_length=20, choices=ST_CHOICES)
    # summa=models.FloatField(null=True, blank=True)
    # tulandi = models.BooleanField(default=False)
    # tasdiq_kutilmoqda = models.BooleanField(default=False)
def yetkazuvchi_mahsulot_filter(Sotuv):
    res=[]
    for s in Sotuv:
        sx=s.smm.split(',')
        t0=''
        t1=''
        t2=''
        
        for i in sx:
            if i.strip():
                n = i.strip().rsplit(' ', 2) # Name Quantity Price
                if len(n) == 3:
                    prod_nom = n[0].strip()
                    if prod_nom not in t0:
                        mahs_obj = Mahsulot.objects.filter(nomi=prod_nom).first()
                        if not mahs_obj:
                            continue # Skip missing products
                        t0 += prod_nom + ' '
                        t1 += prod_nom + ' ' + n[1] + ' ' + str(mahs_obj.turi) + ' '
                        t2 += n[2] + ' '
        print(t0,t1,t2)
        ns=sotuv_new_form([t0,t1,t2],s)
         
        print(ns.narxi)
        res.append( ns)
    
    return res
          
def add_spctoint(x):
    x = str(x)
    if '.' in x:
        int_part, dec_part = x.split('.')
    else:
        int_part, dec_part = x, None

    # Raqamlarni teskari qilib, 3 ta guruhlarga ajratamiz
    s = ''
    for i in range(0, len(int_part[::-1]), 3):
        s += int_part[::-1][i:i+3] + ' '
    formatted = s[::-1].strip()

    if dec_part:
        return f"{formatted}.{dec_part}"
    return formatted
def get_bugungi_savdo_summ(savdolar):
    summa=0
   
    for s in savdolar:
        summa+=s.summa
    
    return add_spctoint(summa)