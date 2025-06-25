from .models import Mahsulot
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


