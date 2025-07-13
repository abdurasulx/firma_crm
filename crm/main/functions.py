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
                turi = mahsulot_obj.turi if mahsulot_obj else "noma'lum"
                narx = mahsulot_obj.narxi if mahsulot_obj else 0

                if nomi not in natija:
                    natija[nomi] = new_yuklama(nomi, miqdor, turi,narx)
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
        if y!='':
            y=y.split(' ')
            natija[y[0]]=int(y[1])
    mahs=mahs.split(',')
    # print(mahs)
    
    for m in mahs:
        if m!='':
            n=m.split(' ')
            # print(m[0])
            if n[0] in  natija:
                    
                ci=natija[n[0]]
                # print(ci,ci-int(n[1]))
                natija[n[0]]=ci-int(n[1])
    sotl=''
    for i in natija:
        if natija[i]>0:
            sotl+=f'{i} {natija[i]},'


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
            
            if i!='':
                n=i.split(' ')
                if n[0] not in t0:
                    t0+=n[0]+' '
                    t1+=n[0]+' '+n[1]+' '+str(Mahsulot.objects.get(nomi=n[0]).turi)+' '
                    t2+=n[2]+' '
        print(t0,t1,t2)
        ns=sotuv_new_form([t0,t1,t2],s)
         
        print(ns.narxi)
        res.append( ns)
    
    return res
          
    