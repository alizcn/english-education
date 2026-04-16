from django.core.management.base import BaseCommand
from django.db import transaction
from apps.topics.models import Topic, TopicExample

TOPICS = [
    {
        'slug': 'present-simple',
        'name': 'Present Simple',
        'explanation': (
            'Genel doğrular, alışkanlıklar ve rutinler için kullanılır. '
            'Yapı: Özne + V1 (he/she/it ile fiile -s eklenir).'
        ),
        'examples': [
            ('positive', 'I drink coffee every morning.', 'Her sabah kahve içerim.'),
            ('positive', 'She works at a hospital.', 'O bir hastanede çalışır.'),
            ('positive', 'We live in Istanbul.', 'Biz İstanbul\'da yaşarız.'),
            ('negative', 'I do not like olives.', 'Zeytin sevmem.'),
            ('negative', 'He does not speak French.', 'O Fransızca konuşmaz.'),
            ('negative', 'They do not work on Sundays.', 'Pazar günleri çalışmazlar.'),
            ('question', 'Do you play football?', 'Futbol oynar mısın?'),
            ('question', 'Does she know the answer?', 'O cevabı biliyor mu?'),
            ('question', 'Where do they live?', 'Onlar nerede yaşar?'),
        ],
    },
    {
        'slug': 'present-continuous',
        'name': 'Present Continuous',
        'explanation': (
            'Şu anda olan ve geçici durumlar için kullanılır. '
            'Yapı: Özne + am/is/are + V-ing.'
        ),
        'examples': [
            ('positive', 'I am reading a book right now.', 'Şu anda kitap okuyorum.'),
            ('positive', 'She is cooking dinner.', 'O akşam yemeği pişiriyor.'),
            ('positive', 'They are studying English.', 'Onlar İngilizce çalışıyor.'),
            ('negative', 'I am not watching TV.', 'Televizyon izlemiyorum.'),
            ('negative', 'He is not sleeping.', 'O uyumuyor.'),
            ('negative', 'We are not working today.', 'Bugün çalışmıyoruz.'),
            ('question', 'Are you listening to me?', 'Beni dinliyor musun?'),
            ('question', 'Is she coming with us?', 'O bizimle geliyor mu?'),
            ('question', 'What are they doing?', 'Onlar ne yapıyor?'),
        ],
    },
    {
        'slug': 'present-perfect',
        'name': 'Present Perfect',
        'explanation': (
            'Geçmişte başlayıp şu ana etkisi süren olaylar için. '
            'Yapı: Özne + have/has + V3.'
        ),
        'examples': [
            ('positive', 'I have finished my homework.', 'Ödevimi bitirdim.'),
            ('positive', 'She has lived here for ten years.', 'O burada on yıldır yaşıyor.'),
            ('positive', 'We have seen that movie.', 'O filmi gördük.'),
            ('negative', 'I have not eaten yet.', 'Henüz yemek yemedim.'),
            ('negative', 'He has not called me.', 'Beni aramadı.'),
            ('negative', 'They have not arrived.', 'Onlar varmadı.'),
            ('question', 'Have you ever been to Paris?', 'Hiç Paris\'e gittin mi?'),
            ('question', 'Has she finished her work?', 'O işini bitirdi mi?'),
            ('question', 'How long have you known him?', 'Onu ne zamandır tanıyorsun?'),
        ],
    },
    {
        'slug': 'present-perfect-continuous',
        'name': 'Present Perfect Continuous',
        'explanation': (
            'Geçmişte başlayıp hâlâ devam eden veya yeni bitmiş sürekli eylemler için. '
            'Yapı: Özne + have/has been + V-ing.'
        ),
        'examples': [
            ('positive', 'I have been working since morning.', 'Sabahtan beri çalışıyorum.'),
            ('positive', 'She has been studying for three hours.', 'Üç saattir ders çalışıyor.'),
            ('positive', 'It has been raining all day.', 'Bütün gün yağmur yağıyor.'),
            ('negative', 'I have not been sleeping well.', 'İyi uyuyamıyorum.'),
            ('negative', 'He has not been feeling well.', 'O kendini iyi hissetmiyor.'),
            ('negative', 'They have not been coming to class.', 'Derse gelmiyorlar.'),
            ('question', 'Have you been waiting long?', 'Uzun süredir mi bekliyorsun?'),
            ('question', 'Has she been crying?', 'O ağlıyor muydu?'),
            ('question', 'What have you been doing lately?', 'Son zamanlarda ne yapıyorsun?'),
        ],
    },
    {
        'slug': 'past-simple',
        'name': 'Past Simple',
        'explanation': (
            'Geçmişte tamamlanmış eylemler için. '
            'Yapı: Özne + V2 (düzensiz fiil) veya V-ed.'
        ),
        'examples': [
            ('positive', 'I went to the cinema yesterday.', 'Dün sinemaya gittim.'),
            ('positive', 'She bought a new car.', 'O yeni bir araba aldı.'),
            ('positive', 'They played football last night.', 'Dün gece futbol oynadılar.'),
            ('negative', 'I did not eat breakfast.', 'Kahvaltı etmedim.'),
            ('negative', 'He did not come to the party.', 'Partiye gelmedi.'),
            ('negative', 'We did not know the answer.', 'Cevabı bilmiyorduk.'),
            ('question', 'Did you see him?', 'Onu gördün mü?'),
            ('question', 'Did she like the gift?', 'O hediyeyi beğendi mi?'),
            ('question', 'Where did they go?', 'Nereye gittiler?'),
        ],
    },
    {
        'slug': 'past-continuous',
        'name': 'Past Continuous',
        'explanation': (
            'Geçmişte belirli bir anda devam eden eylemler için. '
            'Yapı: Özne + was/were + V-ing.'
        ),
        'examples': [
            ('positive', 'I was reading when you called.', 'Sen aradığında okuyordum.'),
            ('positive', 'She was cooking at 7 pm.', 'O saat 19\'da yemek pişiriyordu.'),
            ('positive', 'They were playing in the garden.', 'Bahçede oynuyorlardı.'),
            ('negative', 'I was not listening.', 'Dinlemiyordum.'),
            ('negative', 'He was not working yesterday.', 'Dün çalışmıyordu.'),
            ('negative', 'We were not sleeping.', 'Uyumuyorduk.'),
            ('question', 'Were you watching TV?', 'Televizyon mu izliyordun?'),
            ('question', 'Was she waiting for you?', 'O seni mi bekliyordu?'),
            ('question', 'What were they doing?', 'Ne yapıyorlardı?'),
        ],
    },
    {
        'slug': 'past-perfect',
        'name': 'Past Perfect',
        'explanation': (
            'Geçmişteki iki olaydan önce olanı anlatmak için. '
            'Yapı: Özne + had + V3.'
        ),
        'examples': [
            ('positive', 'She had left before I arrived.', 'Ben varmadan önce o gitmişti.'),
            ('positive', 'They had finished dinner by 8.', '8\'e kadar yemeği bitirmişlerdi.'),
            ('positive', 'I had seen that film before.', 'Filmi daha önce görmüştüm.'),
            ('negative', 'I had not met him before that.', 'Ondan önce onunla tanışmamıştım.'),
            ('negative', 'He had not finished his work.', 'O işini bitirmemişti.'),
            ('negative', 'We had not heard the news.', 'Haberi duymamıştık.'),
            ('question', 'Had you eaten before the meeting?', 'Toplantıdan önce yemek yemiş miydin?'),
            ('question', 'Had she lived there long?', 'Orada uzun süre mi yaşamıştı?'),
            ('question', 'Where had they gone?', 'Nereye gitmişlerdi?'),
        ],
    },
    {
        'slug': 'future-simple-will',
        'name': 'Future Simple (will)',
        'explanation': (
            'Ani kararlar, tahminler ve vaatler için kullanılır. '
            'Yapı: Özne + will + V1.'
        ),
        'examples': [
            ('positive', 'I will help you.', 'Sana yardım edeceğim.'),
            ('positive', 'She will call you tomorrow.', 'O seni yarın arayacak.'),
            ('positive', 'It will rain tonight.', 'Bu gece yağmur yağacak.'),
            ('negative', 'I will not forget you.', 'Seni unutmayacağım.'),
            ('negative', 'He will not come.', 'O gelmeyecek.'),
            ('negative', 'We will not be late.', 'Geç kalmayacağız.'),
            ('question', 'Will you marry me?', 'Benimle evlenir misin?'),
            ('question', 'Will she be there?', 'O orada olacak mı?'),
            ('question', 'When will they arrive?', 'Ne zaman varırlar?'),
        ],
    },
    {
        'slug': 'future-be-going-to',
        'name': 'Future (be going to)',
        'explanation': (
            'Önceden planlanmış kararlar ve kanıta dayalı tahminler için. '
            'Yapı: Özne + am/is/are + going to + V1.'
        ),
        'examples': [
            ('positive', 'I am going to learn Spanish.', 'İspanyolca öğreneceğim.'),
            ('positive', 'She is going to visit her parents.', 'Annesini babasını ziyaret edecek.'),
            ('positive', 'It is going to snow.', 'Kar yağacak.'),
            ('negative', 'I am not going to quit.', 'Bırakmayacağım.'),
            ('negative', 'He is not going to apologize.', 'Özür dilemeyecek.'),
            ('negative', 'We are not going to travel this year.', 'Bu yıl seyahat etmeyeceğiz.'),
            ('question', 'Are you going to eat that?', 'Onu yiyecek misin?'),
            ('question', 'Is she going to join us?', 'Bize katılacak mı?'),
            ('question', 'What are you going to do?', 'Ne yapacaksın?'),
        ],
    },
    {
        'slug': 'modals-can-could',
        'name': 'Modals: can / could',
        'explanation': (
            'Yetenek, izin, rica ve olasılık bildirir. '
            'can = şimdi; could = geçmişte yetenek ya da kibar rica.'
        ),
        'examples': [
            ('positive', 'I can swim.', 'Yüzebilirim.'),
            ('positive', 'She could read at four.', 'O dört yaşında okuyabiliyordu.'),
            ('positive', 'You can use my laptop.', 'Laptopumu kullanabilirsin.'),
            ('negative', 'I cannot drive.', 'Araba kullanamam.'),
            ('negative', 'He could not hear us.', 'Bizi duyamadı.'),
            ('negative', 'We cannot go out tonight.', 'Bu gece dışarı çıkamayız.'),
            ('question', 'Can you help me?', 'Bana yardım edebilir misin?'),
            ('question', 'Could she play the piano?', 'O piyano çalabiliyor muydu?'),
            ('question', 'Can I open the window?', 'Pencereyi açabilir miyim?'),
        ],
    },
    {
        'slug': 'modals-must-should',
        'name': 'Modals: must / should',
        'explanation': (
            'must = zorunluluk / güçlü çıkarım; should = tavsiye.'
        ),
        'examples': [
            ('positive', 'You must wear a seatbelt.', 'Emniyet kemeri takmalısın.'),
            ('positive', 'She should see a doctor.', 'Doktora görünmeli.'),
            ('positive', 'He must be tired.', 'Yorgun olmalı.'),
            ('negative', 'You must not smoke here.', 'Burada sigara içmemelisin.'),
            ('negative', 'You should not eat too much sugar.', 'Çok şeker yememelisin.'),
            ('negative', 'They must not be late.', 'Geç kalmamalılar.'),
            ('question', 'Must I go now?', 'Şimdi gitmek zorunda mıyım?'),
            ('question', 'Should I call her?', 'Onu aramalı mıyım?'),
            ('question', 'Should we book a table?', 'Masa ayırtmalı mıyız?'),
        ],
    },
    {
        'slug': 'conditional-0',
        'name': 'Zero Conditional',
        'explanation': (
            'Her zaman doğru olan genel gerçekler için. '
            'Yapı: If + Present Simple, Present Simple.'
        ),
        'examples': [
            ('positive', 'If you heat water, it boils.', 'Suyu ısıtırsan kaynar.'),
            ('positive', 'If it rains, the ground gets wet.', 'Yağmur yağarsa zemin ıslanır.'),
            ('positive', 'If I drink coffee late, I cannot sleep.', 'Geç kahve içersem uyuyamam.'),
            ('negative', 'If you do not water plants, they die.', 'Bitkileri sulamazsan ölürler.'),
            ('negative', 'If he does not study, he fails.', 'Ders çalışmazsa kalır.'),
            ('negative', 'If we do not leave now, we are late.', 'Şimdi çıkmazsak geç kalırız.'),
            ('question', 'What happens if you press this button?', 'Bu tuşa basarsan ne olur?'),
            ('question', 'Does the alarm ring if someone opens the door?', 'Birisi kapıyı açarsa alarm çalar mı?'),
            ('question', 'If it is cold, do you wear a coat?', 'Hava soğuksa palto giyer misin?'),
        ],
    },
    {
        'slug': 'conditional-1',
        'name': 'First Conditional',
        'explanation': (
            'Gelecekte gerçekleşmesi muhtemel durumlar için. '
            'Yapı: If + Present Simple, will + V1.'
        ),
        'examples': [
            ('positive', 'If it rains, I will stay home.', 'Yağmur yağarsa evde kalacağım.'),
            ('positive', 'If you study, you will pass.', 'Ders çalışırsan geçeceksin.'),
            ('positive', 'If she calls, I will answer.', 'O ararsa cevap veririm.'),
            ('negative', 'If you do not hurry, you will miss the bus.', 'Acele etmezsen otobüsü kaçırırsın.'),
            ('negative', 'If he does not apologize, I will not talk to him.', 'Özür dilemezse onunla konuşmam.'),
            ('negative', 'If we do not leave now, we will not arrive on time.', 'Şimdi gitmezsek zamanında varamayız.'),
            ('question', 'What will you do if it rains?', 'Yağmur yağarsa ne yapacaksın?'),
            ('question', 'Will she come if we invite her?', 'Onu çağırırsak gelir mi?'),
            ('question', 'If I help you, will you help me?', 'Sana yardım edersem bana yardım eder misin?'),
        ],
    },
    {
        'slug': 'conditional-2',
        'name': 'Second Conditional',
        'explanation': (
            'Şu anki veya gelecekteki hayali/imkânsız durumlar için. '
            'Yapı: If + Past Simple, would + V1.'
        ),
        'examples': [
            ('positive', 'If I had money, I would travel the world.', 'Param olsa dünyayı gezerdim.'),
            ('positive', 'If she knew him, she would call.', 'Onu tanısaydı arardı.'),
            ('positive', 'If I were you, I would apologize.', 'Senin yerinde olsam özür dilerdim.'),
            ('negative', 'If I were rich, I would not work.', 'Zengin olsam çalışmazdım.'),
            ('negative', 'If he knew the truth, he would not stay.', 'Gerçeği bilse kalmazdı.'),
            ('negative', 'If we had time, we would not rush.', 'Zamanımız olsa acele etmezdik.'),
            ('question', 'What would you do if you won the lottery?', 'Piyangoyu kazansan ne yapardın?'),
            ('question', 'Would you help me if I asked?', 'İstesem bana yardım eder miydin?'),
            ('question', 'If you could fly, where would you go?', 'Uçabilseydin nereye giderdin?'),
        ],
    },
    {
        'slug': 'conditional-3',
        'name': 'Third Conditional',
        'explanation': (
            'Geçmişte olmamış, hayali durumlar ve pişmanlık için. '
            'Yapı: If + Past Perfect, would have + V3.'
        ),
        'examples': [
            ('positive', 'If I had studied, I would have passed.', 'Ders çalışsaydım geçerdim.'),
            ('positive', 'If she had called me, I would have helped.', 'Beni arasaydı yardım ederdim.'),
            ('positive', 'If they had left earlier, they would have caught the train.', 'Daha erken çıksalardı treni yakalarlardı.'),
            ('negative', 'If you had not helped me, I would not have succeeded.', 'Bana yardım etmeseydin başaramazdım.'),
            ('negative', 'If it had not rained, we would not have stayed home.', 'Yağmur yağmasaydı evde kalmazdık.'),
            ('negative', 'If he had listened, he would not have made the mistake.', 'Dinleseydi bu hatayı yapmazdı.'),
            ('question', 'What would you have done if you had known?', 'Bilseydin ne yapardın?'),
            ('question', 'Would you have come if we had invited you?', 'Seni çağırsaydık gelir miydin?'),
            ('question', 'If she had asked, would you have answered?', 'Sorsaydı cevap verir miydin?'),
        ],
    },
    {
        'slug': 'passive-voice',
        'name': 'Passive Voice',
        'explanation': (
            'Eylemi yapan değil, eylemden etkilenen öne çıkarıldığında. '
            'Yapı: Özne + be (ilgili zamanda) + V3.'
        ),
        'examples': [
            ('positive', 'The cake is eaten.', 'Kek yendi.'),
            ('positive', 'The house was built in 1990.', 'Ev 1990\'da inşa edildi.'),
            ('positive', 'English is spoken here.', 'Burada İngilizce konuşulur.'),
            ('negative', 'The letter was not sent.', 'Mektup gönderilmedi.'),
            ('negative', 'The room is not cleaned every day.', 'Oda her gün temizlenmez.'),
            ('negative', 'The window has not been fixed.', 'Pencere tamir edilmedi.'),
            ('question', 'Was the email sent?', 'E-posta gönderildi mi?'),
            ('question', 'Is this book read by many people?', 'Bu kitap çok kişi tarafından okunur mu?'),
            ('question', 'When was it invented?', 'Ne zaman icat edildi?'),
        ],
    },
    {
        'slug': 'reported-speech',
        'name': 'Reported Speech',
        'explanation': (
            'Başkasının söylediklerini aktarırken kullanılır. Zamanlar bir geri kayar.'
        ),
        'examples': [
            ('positive', 'She said she was tired.', 'Yorgun olduğunu söyledi.'),
            ('positive', 'He told me he had finished the work.', 'Bana işi bitirdiğini söyledi.'),
            ('positive', 'They said they would come.', 'Geleceklerini söylediler.'),
            ('negative', 'He said he did not know.', 'Bilmediğini söyledi.'),
            ('negative', 'She told me she had not seen him.', 'Onu görmediğini söyledi.'),
            ('negative', 'They said they were not hungry.', 'Aç olmadıklarını söylediler.'),
            ('question', 'He asked me where I lived.', 'Bana nerede yaşadığımı sordu.'),
            ('question', 'She asked if I was ready.', 'Hazır olup olmadığımı sordu.'),
            ('question', 'They asked when the meeting would start.', 'Toplantının ne zaman başlayacağını sordular.'),
        ],
    },
    {
        'slug': 'comparatives-superlatives',
        'name': 'Comparatives & Superlatives',
        'explanation': (
            'Karşılaştırma için. Kısa sıfatlara -er/-est, uzun sıfatlara more/most.'
        ),
        'examples': [
            ('positive', 'This book is better than that one.', 'Bu kitap ondan daha iyi.'),
            ('positive', 'She is the tallest in the class.', 'Sınıftaki en uzun boylu o.'),
            ('positive', 'Today is hotter than yesterday.', 'Bugün dünden daha sıcak.'),
            ('negative', 'This is not as expensive as I thought.', 'Bu düşündüğüm kadar pahalı değil.'),
            ('negative', 'He is not the fastest runner.', 'O en hızlı koşucu değil.'),
            ('negative', 'That movie was not as good as this one.', 'O film bunun kadar iyi değildi.'),
            ('question', 'Which is the most interesting?', 'En ilginç olan hangisi?'),
            ('question', 'Is it colder today than yesterday?', 'Bugün dünden daha mı soğuk?'),
            ('question', 'Who is taller, you or your brother?', 'Kim daha uzun, sen mi kardeşin mi?'),
        ],
    },
]


class Command(BaseCommand):
    help = 'Hazır gramer konularını ve örneklerini veritabanına yükler.'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true', help='Önce mevcut konuları sil.')

    def handle(self, *args, **opts):
        if opts.get('reset'):
            Topic.objects.all().delete()
            self.stdout.write(self.style.WARNING('Mevcut konular silindi.'))

        created_topics = 0
        created_examples = 0
        with transaction.atomic():
            for order, t in enumerate(TOPICS):
                topic, was_created = Topic.objects.get_or_create(
                    slug=t['slug'],
                    defaults={
                        'name': t['name'],
                        'explanation': t['explanation'],
                        'order': order,
                    },
                )
                if not was_created:
                    topic.name = t['name']
                    topic.explanation = t['explanation']
                    topic.order = order
                    topic.save()
                else:
                    created_topics += 1

                existing = set(
                    topic.examples.values_list('kind', 'sentence_en')
                )
                for kind, en, tr in t['examples']:
                    if (kind, en) in existing:
                        continue
                    TopicExample.objects.create(
                        topic=topic, kind=kind, sentence_en=en, sentence_tr=tr,
                    )
                    created_examples += 1

        self.stdout.write(self.style.SUCCESS(
            f'Bitti. Yeni konu: {created_topics}, yeni örnek: {created_examples}.'
        ))
