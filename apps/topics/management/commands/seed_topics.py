from django.core.management.base import BaseCommand
from django.db import transaction
from apps.topics.models import Topic, TopicExample

TOPICS = [
    {
        'slug': 'present-simple',
        'name': 'Present Simple',
        'explanation': (
            'Present Simple (Geniş Zaman) genel doğruları, alışkanlıkları, rutinleri ve kalıcı durumları anlatmak için kullanılır.\n\n'
            'NE ZAMAN KULLANILIR?\n'
            '• Alışkanlıklar ve rutinler: I go to the gym every Monday.\n'
            '• Genel gerçekler ve bilimsel doğrular: Water boils at 100°C.\n'
            '• Kalıcı durumlar ve meslekler: She teaches English.\n'
            '• Program / zaman çizelgesi: The train leaves at 9 am.\n\n'
            'YAPI\n'
            '• Olumlu: Özne + V1 (he/she/it ile fiile -s / -es eklenir)\n'
            '    I work · She works · They work\n'
            '• Olumsuz: Özne + do/does + not + V1\n'
            '    I do not (don\'t) work · She does not (doesn\'t) work\n'
            '• Soru: Do/Does + özne + V1?\n'
            '    Do you work? · Does she work?\n\n'
            'SIK GÖRÜLEN ZAMAN ZARFLARI\n'
            'always, usually, often, sometimes, never, every day, on Mondays, twice a week\n\n'
            'İPUÇLARI\n'
            '• 3. tekil şahısta (he/she/it) fiile -s eklemeyi unutma.\n'
            '• Olumsuz ve soru cümlelerinde fiil YALIN hâlde kalır: She doesn\'t WORKS ❌ → She doesn\'t WORK ✅\n'
            '• "have" fiilinin 3. tekil hâli "has"tır.'
        ),
        'examples': [
            ('positive', 'I drink coffee every morning.', 'Her sabah kahve içerim.'),
            ('positive', 'She works at a hospital.', 'O bir hastanede çalışır.'),
            ('positive', 'We live in Istanbul.', 'Biz İstanbul\'da yaşarız.'),
            ('positive', 'The sun rises in the east.', 'Güneş doğudan doğar.'),
            ('positive', 'My brother speaks three languages.', 'Kardeşim üç dil konuşur.'),
            ('positive', 'The train arrives at 7:30 every morning.', 'Tren her sabah 7:30\'da gelir.'),
            ('negative', 'I do not like olives.', 'Zeytin sevmem.'),
            ('negative', 'He does not speak French.', 'O Fransızca konuşmaz.'),
            ('negative', 'They do not work on Sundays.', 'Pazar günleri çalışmazlar.'),
            ('negative', 'She does not eat meat.', 'O et yemez.'),
            ('negative', 'We do not watch TV in the morning.', 'Sabahları televizyon izlemeyiz.'),
            ('negative', 'The shop does not open on Mondays.', 'Dükkan pazartesileri açmaz.'),
            ('question', 'Do you play football?', 'Futbol oynar mısın?'),
            ('question', 'Does she know the answer?', 'O cevabı biliyor mu?'),
            ('question', 'Where do they live?', 'Onlar nerede yaşar?'),
            ('question', 'What time does the meeting start?', 'Toplantı saat kaçta başlar?'),
            ('question', 'How often do you exercise?', 'Ne sıklıkla spor yaparsın?'),
            ('question', 'Does your father work in this city?', 'Baban bu şehirde mi çalışır?'),
        ],
    },
    {
        'slug': 'present-continuous',
        'name': 'Present Continuous',
        'explanation': (
            'Present Continuous (Şimdiki Zaman), tam şu anda veya bu günlerde devam eden geçici eylemleri anlatmak için kullanılır.\n\n'
            'NE ZAMAN KULLANILIR?\n'
            '• Konuşma anında süren eylem: I am reading a book right now.\n'
            '• Bu günlerde geçici olarak yaptığımız şeyler: She is studying for her exam this week.\n'
            '• Kesinleşmiş gelecek planları: We are meeting Ali tomorrow.\n'
            '• Değişen / gelişen durumlar: The weather is getting colder.\n\n'
            'YAPI\n'
            '• Olumlu: Özne + am/is/are + V-ing\n'
            '    I am working · She is working · They are working\n'
            '• Olumsuz: Özne + am/is/are + not + V-ing\n'
            '    I am not working · He isn\'t working\n'
            '• Soru: Am/Is/Are + özne + V-ing?\n'
            '    Are you working? · Is she working?\n\n'
            'SIK GÖRÜLEN ZAMAN İFADELERİ\n'
            'now, right now, at the moment, currently, these days, today, this week\n\n'
            'İPUÇLARI\n'
            '• Fiil sonu -e ile bitiyorsa e düşer: make → making, have → having.\n'
            '• Tek heceli ünlü+ünsüz bitişlerde son ünsüz çift yazılır: run → running, swim → swimming.\n'
            '• Durağan fiiller (know, believe, love, understand, own, belong...) genelde continuous\'ta kullanılmaz.'
        ),
        'examples': [
            ('positive', 'I am reading a book right now.', 'Şu anda kitap okuyorum.'),
            ('positive', 'She is cooking dinner.', 'O akşam yemeği pişiriyor.'),
            ('positive', 'They are studying English.', 'Onlar İngilizce çalışıyor.'),
            ('positive', 'The baby is sleeping peacefully.', 'Bebek huzurlu bir şekilde uyuyor.'),
            ('positive', 'We are having lunch at the new café.', 'Yeni kafede öğle yemeği yiyoruz.'),
            ('positive', 'It is raining heavily outside.', 'Dışarıda şiddetli yağmur yağıyor.'),
            ('negative', 'I am not watching TV.', 'Televizyon izlemiyorum.'),
            ('negative', 'He is not sleeping.', 'O uyumuyor.'),
            ('negative', 'We are not working today.', 'Bugün çalışmıyoruz.'),
            ('negative', 'They are not listening to the teacher.', 'Öğretmeni dinlemiyorlar.'),
            ('negative', 'She is not feeling well today.', 'O bugün kendini iyi hissetmiyor.'),
            ('negative', 'I am not using my phone right now.', 'Şu an telefonumu kullanmıyorum.'),
            ('question', 'Are you listening to me?', 'Beni dinliyor musun?'),
            ('question', 'Is she coming with us?', 'O bizimle geliyor mu?'),
            ('question', 'What are they doing?', 'Onlar ne yapıyor?'),
            ('question', 'Why is the baby crying?', 'Bebek neden ağlıyor?'),
            ('question', 'Are your parents visiting you this weekend?', 'Ailen bu hafta sonu seni ziyaret ediyor mu?'),
            ('question', 'Is it still snowing outside?', 'Dışarıda hâlâ kar yağıyor mu?'),
        ],
    },
    {
        'slug': 'present-perfect',
        'name': 'Present Perfect',
        'explanation': (
            'Present Perfect, geçmişte başlayıp şu ana kadar etkisi süren ya da şimdiyle bağlantısı olan olayları anlatmak için kullanılır.\n\n'
            'NE ZAMAN KULLANILIR?\n'
            '• Geçmişte belirsiz zamanda yaşanan deneyim: I have been to Paris. (ne zaman olduğu önemli değil)\n'
            '• Geçmişte başlamış, hâlâ süren durum: She has lived here for ten years.\n'
            '• Yeni tamamlanmış, sonucu hâlâ ortada olan eylem: I have just finished my homework.\n'
            '• Şu ana kadar kaç kez: He has visited us three times.\n\n'
            'YAPI\n'
            '• Olumlu: Özne + have/has + V3\n'
            '    I have eaten · She has eaten\n'
            '• Olumsuz: Özne + have/has + not + V3\n'
            '    I haven\'t eaten · He hasn\'t eaten\n'
            '• Soru: Have/Has + özne + V3?\n'
            '    Have you eaten? · Has she eaten?\n\n'
            'ANAHTAR KELİMELER\n'
            'just, already, yet, ever, never, since, for, so far, recently, up to now\n\n'
            'İPUÇLARI\n'
            '• "yet" olumsuz ve soruda, "already" olumluda kullanılır.\n'
            '• "for + süre" (for 5 years), "since + başlangıç" (since 2010).\n'
            '• Belirli geçmiş zaman (yesterday, in 2019, last week) Present Perfect ile kullanılmaz — onlar Past Simple gerektirir.'
        ),
        'examples': [
            ('positive', 'I have finished my homework.', 'Ödevimi bitirdim.'),
            ('positive', 'She has lived here for ten years.', 'O burada on yıldır yaşıyor.'),
            ('positive', 'We have seen that movie.', 'O filmi gördük.'),
            ('positive', 'He has just called you.', 'Az önce seni aradı.'),
            ('positive', 'They have already eaten dinner.', 'Akşam yemeğini çoktan yediler.'),
            ('positive', 'I have visited three countries this year.', 'Bu yıl üç ülke ziyaret ettim.'),
            ('negative', 'I have not eaten yet.', 'Henüz yemek yemedim.'),
            ('negative', 'He has not called me.', 'Beni aramadı.'),
            ('negative', 'They have not arrived.', 'Onlar varmadı.'),
            ('negative', 'She has not seen the new film.', 'Yeni filmi görmedi.'),
            ('negative', 'We have not received the package.', 'Paketi almadık.'),
            ('negative', 'I have never been to Japan.', 'Hiç Japonya\'ya gitmedim.'),
            ('question', 'Have you ever been to Paris?', 'Hiç Paris\'e gittin mi?'),
            ('question', 'Has she finished her work?', 'O işini bitirdi mi?'),
            ('question', 'How long have you known him?', 'Onu ne zamandır tanıyorsun?'),
            ('question', 'Have they left the office already?', 'Ofisten çoktan çıktılar mı?'),
            ('question', 'How many times have you seen that movie?', 'O filmi kaç kez gördün?'),
            ('question', 'Has it stopped raining yet?', 'Yağmur durdu mu?'),
        ],
    },
    {
        'slug': 'present-perfect-continuous',
        'name': 'Present Perfect Continuous',
        'explanation': (
            'Present Perfect Continuous, geçmişte başlamış ve hâlâ süren ya da çok yakın zamanda bitmiş ama sonucu gözle görülür olan eylemleri anlatmak için kullanılır.\n\n'
            'NE ZAMAN KULLANILIR?\n'
            '• Geçmişte başlayıp hâlâ süren eylem: I have been working since morning.\n'
            '• Süre vurgusu: She has been studying for three hours.\n'
            '• Yeni bitmiş ama etkisi kalan eylem: Your eyes are red — have you been crying?\n\n'
            'YAPI\n'
            '• Olumlu: Özne + have/has been + V-ing\n'
            '    I have been waiting · She has been waiting\n'
            '• Olumsuz: Özne + have/has not been + V-ing\n'
            '    I haven\'t been waiting\n'
            '• Soru: Have/Has + özne + been + V-ing?\n'
            '    Have you been waiting?\n\n'
            'ANAHTAR KELİMELER\n'
            'for, since, all day, lately, recently, how long\n\n'
            'FARKI\n'
            '• Present Perfect "ne yaptım" sonucuna odaklanır: I have read the book.\n'
            '• Present Perfect Continuous "ne kadar süredir yapıyorum" sürecine odaklanır: I have been reading for two hours.'
        ),
        'examples': [
            ('positive', 'I have been working since morning.', 'Sabahtan beri çalışıyorum.'),
            ('positive', 'She has been studying for three hours.', 'Üç saattir ders çalışıyor.'),
            ('positive', 'It has been raining all day.', 'Bütün gün yağmur yağıyor.'),
            ('positive', 'We have been living in this city for five years.', 'Bu şehirde beş yıldır yaşıyoruz.'),
            ('positive', 'He has been learning Spanish since January.', 'Ocak\'tan beri İspanyolca öğreniyor.'),
            ('positive', 'They have been renovating the house for a month.', 'Bir aydır evi yeniliyorlar.'),
            ('negative', 'I have not been sleeping well.', 'İyi uyuyamıyorum.'),
            ('negative', 'He has not been feeling well.', 'O kendini iyi hissetmiyor.'),
            ('negative', 'They have not been coming to class.', 'Derse gelmiyorlar.'),
            ('negative', 'She has not been practicing the piano lately.', 'Son zamanlarda piyano çalışmıyor.'),
            ('negative', 'We have not been eating out much.', 'Son zamanlarda pek dışarıda yemiyoruz.'),
            ('negative', 'I have not been using that app recently.', 'Son zamanlarda o uygulamayı kullanmıyorum.'),
            ('question', 'Have you been waiting long?', 'Uzun süredir mi bekliyorsun?'),
            ('question', 'Has she been crying?', 'O ağlıyor muydu?'),
            ('question', 'What have you been doing lately?', 'Son zamanlarda ne yapıyorsun?'),
            ('question', 'How long have they been dating?', 'Ne zamandır çıkıyorlar?'),
            ('question', 'Has it been snowing since last night?', 'Dün geceden beri kar mı yağıyor?'),
            ('question', 'Why have you been avoiding me?', 'Neden benden kaçıyorsun?'),
        ],
    },
    {
        'slug': 'past-simple',
        'name': 'Past Simple',
        'explanation': (
            'Past Simple (Geçmiş Zaman), geçmişte belirli bir zamanda başlamış ve bitmiş eylemleri anlatır.\n\n'
            'NE ZAMAN KULLANILIR?\n'
            '• Geçmişte tamamlanmış olay: I visited my grandmother yesterday.\n'
            '• Geçmişte bir dönem: He worked there from 2015 to 2020.\n'
            '• Sıralı eylemler: She woke up, had breakfast, and went to work.\n'
            '• Geçmiş alışkanlıklar: We played in the park every summer.\n\n'
            'YAPI\n'
            '• Olumlu: Özne + V2 (düzensiz fiil) veya V-ed\n'
            '    I worked · She went · They ate\n'
            '• Olumsuz: Özne + did + not + V1\n'
            '    I did not (didn\'t) work · She didn\'t go\n'
            '• Soru: Did + özne + V1?\n'
            '    Did you work? · Did she go?\n\n'
            'ANAHTAR ZAMAN İFADELERİ\n'
            'yesterday, last week, last year, two days ago, in 1990, when I was a child\n\n'
            'İPUÇLARI\n'
            '• Düzensiz fiil listesi ezberlenmelidir: go-went, see-saw, have-had, take-took...\n'
            '• Olumsuz ve soruda fiil YALIN hâlde kalır: She didn\'t WENT ❌ → She didn\'t GO ✅\n'
            '• Belirli geçmiş zaman işaretleri (ago, yesterday) Present Perfect yerine Past Simple gerektirir.'
        ),
        'examples': [
            ('positive', 'I went to the cinema yesterday.', 'Dün sinemaya gittim.'),
            ('positive', 'She bought a new car.', 'O yeni bir araba aldı.'),
            ('positive', 'They played football last night.', 'Dün gece futbol oynadılar.'),
            ('positive', 'We visited Rome two years ago.', 'İki yıl önce Roma\'yı ziyaret ettik.'),
            ('positive', 'He finished his project on time.', 'Projesini zamanında bitirdi.'),
            ('positive', 'The movie ended at 10 pm.', 'Film saat 10\'da bitti.'),
            ('negative', 'I did not eat breakfast.', 'Kahvaltı etmedim.'),
            ('negative', 'He did not come to the party.', 'Partiye gelmedi.'),
            ('negative', 'We did not know the answer.', 'Cevabı bilmiyorduk.'),
            ('negative', 'She did not call me back.', 'O beni geri aramadı.'),
            ('negative', 'They did not finish the homework.', 'Ödevi bitirmediler.'),
            ('negative', 'I did not see him at school yesterday.', 'Onu dün okulda görmedim.'),
            ('question', 'Did you see him?', 'Onu gördün mü?'),
            ('question', 'Did she like the gift?', 'O hediyeyi beğendi mi?'),
            ('question', 'Where did they go?', 'Nereye gittiler?'),
            ('question', 'What time did the meeting start?', 'Toplantı saat kaçta başladı?'),
            ('question', 'Why did he leave so early?', 'Neden bu kadar erken ayrıldı?'),
            ('question', 'Did your parents enjoy the holiday?', 'Ailen tatilin tadını çıkardı mı?'),
        ],
    },
    {
        'slug': 'past-continuous',
        'name': 'Past Continuous',
        'explanation': (
            'Past Continuous (Geçmişte Şimdiki Zaman), geçmişte belirli bir anda devam etmekte olan eylemleri anlatır.\n\n'
            'NE ZAMAN KULLANILIR?\n'
            '• Geçmişte belirli bir anda süren eylem: At 8 pm last night, I was watching TV.\n'
            '• Paralel süren iki eylem: While I was studying, my brother was playing games.\n'
            '• Kesilen uzun eylem (Past Continuous) + kesen kısa eylem (Past Simple):\n'
            '    I was cooking when the phone rang.\n'
            '• Arka plan / atmosfer betimlemesi: The sun was shining and birds were singing.\n\n'
            'YAPI\n'
            '• Olumlu: Özne + was/were + V-ing\n'
            '    I was reading · They were reading\n'
            '• Olumsuz: Özne + was/were + not + V-ing\n'
            '    He wasn\'t listening\n'
            '• Soru: Was/Were + özne + V-ing?\n'
            '    Were you watching? · Was she sleeping?\n\n'
            'ANAHTAR KELİMELER\n'
            'while, when, as, at that moment, all day, at 8 pm yesterday'
        ),
        'examples': [
            ('positive', 'I was reading when you called.', 'Sen aradığında okuyordum.'),
            ('positive', 'She was cooking at 7 pm.', 'O saat 19\'da yemek pişiriyordu.'),
            ('positive', 'They were playing in the garden.', 'Bahçede oynuyorlardı.'),
            ('positive', 'It was raining when we left home.', 'Evden çıktığımızda yağmur yağıyordu.'),
            ('positive', 'The children were laughing loudly.', 'Çocuklar yüksek sesle gülüyorlardı.'),
            ('positive', 'While I was driving, I saw an old friend.', 'Araba sürerken eski bir arkadaşımı gördüm.'),
            ('negative', 'I was not listening.', 'Dinlemiyordum.'),
            ('negative', 'He was not working yesterday.', 'Dün çalışmıyordu.'),
            ('negative', 'We were not sleeping.', 'Uyumuyorduk.'),
            ('negative', 'She was not feeling well yesterday.', 'Dün kendini iyi hissetmiyordu.'),
            ('negative', 'They were not paying attention in class.', 'Derste dikkat etmiyorlardı.'),
            ('negative', 'The shops were not open at that hour.', 'O saatte dükkanlar açık değildi.'),
            ('question', 'Were you watching TV?', 'Televizyon mu izliyordun?'),
            ('question', 'Was she waiting for you?', 'O seni mi bekliyordu?'),
            ('question', 'What were they doing?', 'Ne yapıyorlardı?'),
            ('question', 'Were the kids sleeping when you arrived?', 'Sen vardığında çocuklar uyuyor muydu?'),
            ('question', 'What were you doing at midnight?', 'Gece yarısı ne yapıyordun?'),
            ('question', 'Was it snowing when you left the office?', 'Ofisten çıktığında kar mı yağıyordu?'),
        ],
    },
    {
        'slug': 'past-perfect',
        'name': 'Past Perfect',
        'explanation': (
            'Past Perfect (Geçmişte Geçmiş), geçmişteki iki olaydan daha önce gerçekleşeni anlatır. "Miş"li geçmişe yakın bir yapıdır.\n\n'
            'NE ZAMAN KULLANILIR?\n'
            '• Geçmişteki bir olaydan önceki başka bir olay:\n'
            '    When I arrived, she had already left. (Ben varmadan ÖNCE o gitmişti)\n'
            '• Zaman sıralamasını netleştirme: By 8 pm they had finished dinner.\n'
            '• Reported Speech\'te Past Simple\'dan geri kaydırma.\n\n'
            'YAPI\n'
            '• Olumlu: Özne + had + V3\n'
            '    I had eaten · She had gone\n'
            '• Olumsuz: Özne + had + not + V3\n'
            '    I hadn\'t eaten\n'
            '• Soru: Had + özne + V3?\n'
            '    Had you eaten?\n\n'
            'ANAHTAR KELİMELER\n'
            'already, just, yet, by the time, before, after, when, until\n\n'
            'İPUÇLARI\n'
            '• Tek bir geçmiş olaydan bahsediyorsan Past Simple yeterlidir — iki olay varsa hangisinin "daha önce" olduğunu göstermek için Past Perfect kullanırsın.'
        ),
        'examples': [
            ('positive', 'She had left before I arrived.', 'Ben varmadan önce o gitmişti.'),
            ('positive', 'They had finished dinner by 8.', '8\'e kadar yemeği bitirmişlerdi.'),
            ('positive', 'I had seen that film before.', 'Filmi daha önce görmüştüm.'),
            ('positive', 'By the time we got there, the game had ended.', 'Oraya vardığımızda maç bitmişti.'),
            ('positive', 'He had studied English for ten years before moving abroad.', 'Yurt dışına taşınmadan önce on yıl İngilizce çalışmıştı.'),
            ('positive', 'When the police arrived, the thief had already escaped.', 'Polis vardığında hırsız çoktan kaçmıştı.'),
            ('negative', 'I had not met him before that.', 'Ondan önce onunla tanışmamıştım.'),
            ('negative', 'He had not finished his work.', 'O işini bitirmemişti.'),
            ('negative', 'We had not heard the news.', 'Haberi duymamıştık.'),
            ('negative', 'She had not been to Europe before 2020.', '2020\'den önce Avrupa\'ya gitmemişti.'),
            ('negative', 'They had not spoken to each other for years.', 'Yıllardır birbiriyle konuşmamışlardı.'),
            ('negative', 'I had not realized how late it was.', 'Ne kadar geç olduğunun farkına varmamıştım.'),
            ('question', 'Had you eaten before the meeting?', 'Toplantıdan önce yemek yemiş miydin?'),
            ('question', 'Had she lived there long?', 'Orada uzun süre mi yaşamıştı?'),
            ('question', 'Where had they gone?', 'Nereye gitmişlerdi?'),
            ('question', 'Had he finished the book before the exam?', 'Sınavdan önce kitabı bitirmiş miydi?'),
            ('question', 'What had happened before the alarm went off?', 'Alarm çalmadan önce ne olmuştu?'),
            ('question', 'Had the movie started when you got there?', 'Oraya vardığında film başlamış mıydı?'),
        ],
    },
    {
        'slug': 'future-simple-will',
        'name': 'Future Simple (will)',
        'explanation': (
            'Future Simple "will", geleceğe dair tahminler, ani kararlar, vaatler ve teklifler için kullanılır.\n\n'
            'NE ZAMAN KULLANILIR?\n'
            '• Ani / konuşma anında alınan karar: I\'m thirsty — I\'ll get some water.\n'
            '• Tahmin: It will rain tonight.\n'
            '• Vaat ve söz: I will always love you.\n'
            '• Yardım teklifi / istekte bulunma: I will help you. / Will you pass the salt?\n\n'
            'YAPI\n'
            '• Olumlu: Özne + will + V1 (I\'ll / she\'ll / they\'ll)\n'
            '• Olumsuz: Özne + will not (won\'t) + V1\n'
            '• Soru: Will + özne + V1?\n\n'
            'İPUÇLARI\n'
            '• Önceden plan yaptığın bir şey için "be going to" daha uygundur: I am going to study tonight.\n'
            '• Zaman yan cümlelerinde will KULLANILMAZ: When he arrives (değil "will arrive"), I will call you.'
        ),
        'examples': [
            ('positive', 'I will help you.', 'Sana yardım edeceğim.'),
            ('positive', 'She will call you tomorrow.', 'O seni yarın arayacak.'),
            ('positive', 'It will rain tonight.', 'Bu gece yağmur yağacak.'),
            ('positive', 'I\'m sure he will pass the exam.', 'Eminim sınavı geçecek.'),
            ('positive', 'We will meet at the cafe at 5.', '5\'te kafede buluşacağız.'),
            ('positive', 'Don\'t worry, I will handle it.', 'Merak etme, ben hallederim.'),
            ('negative', 'I will not forget you.', 'Seni unutmayacağım.'),
            ('negative', 'He will not come.', 'O gelmeyecek.'),
            ('negative', 'We will not be late.', 'Geç kalmayacağız.'),
            ('negative', 'She won\'t tell anyone.', 'Kimseye söylemeyecek.'),
            ('negative', 'They will not accept this offer.', 'Bu teklifi kabul etmeyecekler.'),
            ('negative', 'The meeting won\'t last long.', 'Toplantı uzun sürmeyecek.'),
            ('question', 'Will you marry me?', 'Benimle evlenir misin?'),
            ('question', 'Will she be there?', 'O orada olacak mı?'),
            ('question', 'When will they arrive?', 'Ne zaman varırlar?'),
            ('question', 'Will you help me with this?', 'Bu konuda bana yardım eder misin?'),
            ('question', 'How will we get home tonight?', 'Bu gece eve nasıl döneceğiz?'),
            ('question', 'Will the shops be open on Sunday?', 'Pazar günü dükkanlar açık olacak mı?'),
        ],
    },
    {
        'slug': 'future-be-going-to',
        'name': 'Future (be going to)',
        'explanation': (
            '"be going to", önceden planlanmış gelecek niyetleri ve şu ana kadarki kanıtlara dayanan tahminler için kullanılır.\n\n'
            'NE ZAMAN KULLANILIR?\n'
            '• Önceden karar verilmiş plan: I am going to travel to Italy next month.\n'
            '• Gözle görülür kanıta dayalı tahmin: Look at those clouds — it is going to rain.\n\n'
            'YAPI\n'
            '• Olumlu: Özne + am/is/are + going to + V1\n'
            '    I am going to study · She is going to study\n'
            '• Olumsuz: Özne + am/is/are + not + going to + V1\n'
            '• Soru: Am/Is/Are + özne + going to + V1?\n\n'
            'WILL vs BE GOING TO\n'
            '• "will": ani karar, tahmin (genel), vaat\n'
            '• "be going to": önceden plan, görünür kanıta dayalı tahmin\n'
            '• Günlük konuşmada çoğu zaman birbirlerinin yerine kullanılabilir.'
        ),
        'examples': [
            ('positive', 'I am going to learn Spanish.', 'İspanyolca öğreneceğim.'),
            ('positive', 'She is going to visit her parents.', 'Annesini babasını ziyaret edecek.'),
            ('positive', 'It is going to snow.', 'Kar yağacak.'),
            ('positive', 'We are going to buy a new car next year.', 'Gelecek yıl yeni bir araba alacağız.'),
            ('positive', 'He is going to propose to her tonight.', 'Bu gece ona evlenme teklif edecek.'),
            ('positive', 'Look at the sky — it\'s going to storm.', 'Gökyüzüne bak — fırtına olacak.'),
            ('negative', 'I am not going to quit.', 'Bırakmayacağım.'),
            ('negative', 'He is not going to apologize.', 'Özür dilemeyecek.'),
            ('negative', 'We are not going to travel this year.', 'Bu yıl seyahat etmeyeceğiz.'),
            ('negative', 'She isn\'t going to join the project.', 'Projeye katılmayacak.'),
            ('negative', 'They are not going to sell the house.', 'Evi satmayacaklar.'),
            ('negative', 'I\'m not going to wait any longer.', 'Daha fazla beklemeyeceğim.'),
            ('question', 'Are you going to eat that?', 'Onu yiyecek misin?'),
            ('question', 'Is she going to join us?', 'Bize katılacak mı?'),
            ('question', 'What are you going to do?', 'Ne yapacaksın?'),
            ('question', 'Are they going to move to another city?', 'Başka bir şehre taşınacaklar mı?'),
            ('question', 'When is she going to start her new job?', 'Yeni işine ne zaman başlayacak?'),
            ('question', 'Is it going to rain tomorrow?', 'Yarın yağmur yağacak mı?'),
        ],
    },
    {
        'slug': 'modals-can-could',
        'name': 'Modals: can / could',
        'explanation': (
            '"can" ve "could" yetenek, izin, rica ve olasılık bildiren yardımcı (modal) fiillerdir.\n\n'
            'KULLANIMLARI\n'
            '• can → şu anki yetenek: I can swim.\n'
            '• could → geçmiş yetenek: When I was young, I could run fast.\n'
            '• can / could → izin: Can I open the window? / Could I open the window? (could daha kibar)\n'
            '• can / could → rica: Can you help me? / Could you help me? (could daha kibar)\n'
            '• could → nazik / belirsiz olasılık: It could rain tomorrow.\n\n'
            'YAPI\n'
            '• Olumlu: Özne + can / could + V1\n'
            '• Olumsuz: Özne + cannot (can\'t) / could not (couldn\'t) + V1\n'
            '• Soru: Can / Could + özne + V1?\n\n'
            'İPUÇLARI\n'
            '• Modaldan sonra fiil yalın kalır: She can WORKS ❌ → She can WORK ✅\n'
            '• "could have + V3" yapısı geçmişte olması mümkündü ama olmamış anlamındadır: You could have called me.'
        ),
        'examples': [
            ('positive', 'I can swim.', 'Yüzebilirim.'),
            ('positive', 'She could read when she was four.', 'O dört yaşında okuyabiliyordu.'),
            ('positive', 'You can use my laptop.', 'Laptopumu kullanabilirsin.'),
            ('positive', 'He can speak four languages fluently.', 'Dört dili akıcı konuşabiliyor.'),
            ('positive', 'We could hear the music from outside.', 'Müziği dışarıdan duyabiliyorduk.'),
            ('positive', 'I can pick you up from the airport.', 'Seni havalimanından alabilirim.'),
            ('negative', 'I cannot drive.', 'Araba kullanamam.'),
            ('negative', 'He could not hear us.', 'Bizi duyamadı.'),
            ('negative', 'We cannot go out tonight.', 'Bu gece dışarı çıkamayız.'),
            ('negative', 'She can\'t come to the meeting.', 'Toplantıya gelemez.'),
            ('negative', 'They couldn\'t find the address.', 'Adresi bulamadılar.'),
            ('negative', 'I can\'t remember his name.', 'Adını hatırlayamıyorum.'),
            ('question', 'Can you help me?', 'Bana yardım edebilir misin?'),
            ('question', 'Could she play the piano?', 'O piyano çalabiliyor muydu?'),
            ('question', 'Can I open the window?', 'Pencereyi açabilir miyim?'),
            ('question', 'Could you repeat that, please?', 'Bunu tekrar eder misiniz, lütfen?'),
            ('question', 'Can your brother swim well?', 'Kardeşin iyi yüzebilir mi?'),
            ('question', 'Could we meet tomorrow?', 'Yarın buluşabilir miyiz?'),
        ],
    },
    {
        'slug': 'modals-must-should',
        'name': 'Modals: must / should',
        'explanation': (
            '"must" güçlü zorunluluk ve mantıksal çıkarım; "should" tavsiye ve beklenti bildirir.\n\n'
            'KULLANIMLARI\n'
            '• must → zorunluluk (içten gelen): I must finish this report today.\n'
            '• must → kuvvetli mantıksal çıkarım: He must be tired. (kesin bir tahmin)\n'
            '• must not → yasaklama: You must not smoke here.\n'
            '• should → tavsiye: You should exercise more.\n'
            '• should → beklenti: The train should arrive at 8.\n'
            '• should not → tavsiye edilmeyen: You shouldn\'t eat so much sugar.\n\n'
            'YAPI\n'
            '• Özne + must / should + V1\n'
            '• Olumsuz: must not (mustn\'t) / should not (shouldn\'t) + V1\n'
            '• Soru: Must / Should + özne + V1?\n\n'
            'MUST vs HAVE TO\n'
            '• must: kişinin kendi içinden gelen zorunluluk veya kural\n'
            '• have to: dışarıdan gelen zorunluluk (kurallar, iş vs.)\n'
            '• Olumsuzda farklıdır: "mustn\'t" = yasak / "don\'t have to" = gerekmez'
        ),
        'examples': [
            ('positive', 'You must wear a seatbelt.', 'Emniyet kemeri takmalısın.'),
            ('positive', 'She should see a doctor.', 'Doktora görünmeli.'),
            ('positive', 'He must be tired.', 'Yorgun olmalı.'),
            ('positive', 'Students must submit the assignment by Friday.', 'Öğrenciler ödevi cuma gününe kadar teslim etmeli.'),
            ('positive', 'You should try the new restaurant downtown.', 'Şehir merkezindeki yeni restoranı denemelisin.'),
            ('positive', 'We must leave now to catch the train.', 'Treni yakalamak için şimdi çıkmalıyız.'),
            ('negative', 'You must not smoke here.', 'Burada sigara içmemelisin.'),
            ('negative', 'You should not eat too much sugar.', 'Çok şeker yememelisin.'),
            ('negative', 'They must not be late.', 'Geç kalmamalılar.'),
            ('negative', 'You shouldn\'t worry about small things.', 'Küçük şeyler için endişelenmemelisin.'),
            ('negative', 'Visitors must not enter without a badge.', 'Ziyaretçiler kart olmadan girmemeli.'),
            ('negative', 'He shouldn\'t speak to her like that.', 'Onunla böyle konuşmamalı.'),
            ('question', 'Must I go now?', 'Şimdi gitmek zorunda mıyım?'),
            ('question', 'Should I call her?', 'Onu aramalı mıyım?'),
            ('question', 'Should we book a table?', 'Masa ayırtmalı mıyız?'),
            ('question', 'Must they wear a uniform?', 'Üniforma giymek zorundalar mı?'),
            ('question', 'Should I apply for this job?', 'Bu işe başvurmalı mıyım?'),
            ('question', 'Must the report be ready by Monday?', 'Rapor pazartesiye hazır olmak zorunda mı?'),
        ],
    },
    {
        'slug': 'conditional-0',
        'name': 'Zero Conditional',
        'explanation': (
            'Zero Conditional, her zaman doğru olan gerçekleri, bilimsel doğruları ve genel kuralları anlatmak için kullanılır.\n\n'
            'NE ZAMAN KULLANILIR?\n'
            '• Bilimsel gerçekler: If you heat water to 100°C, it boils.\n'
            '• Genel doğrular: If it rains, the ground gets wet.\n'
            '• Kurallar / talimatlar: If you press this button, the door opens.\n\n'
            'YAPI\n'
            '• If + Present Simple, Present Simple.\n'
            '    If you mix red and blue, you get purple.\n'
            '• Sıralama değişebilir:\n'
            '    You get purple if you mix red and blue.\n\n'
            'İPUÇLARI\n'
            '• "if" yerine "when" de kullanılabilir çünkü olay neredeyse kesindir:\n'
            '    When you heat water, it boils.\n'
            '• "will" veya "would" YOKTUR — Zero Conditional\'da her iki tarafta da Present Simple vardır.'
        ),
        'examples': [
            ('positive', 'If you heat water, it boils.', 'Suyu ısıtırsan kaynar.'),
            ('positive', 'If it rains, the ground gets wet.', 'Yağmur yağarsa zemin ıslanır.'),
            ('positive', 'If I drink coffee late, I cannot sleep.', 'Geç kahve içersem uyuyamam.'),
            ('positive', 'If the sun goes down, it gets dark.', 'Güneş batarsa hava kararır.'),
            ('positive', 'If you mix red and yellow, you get orange.', 'Kırmızı ve sarıyı karıştırırsan turuncu olur.'),
            ('positive', 'If people eat too much, they gain weight.', 'İnsanlar fazla yerse kilo alır.'),
            ('negative', 'If you do not water plants, they die.', 'Bitkileri sulamazsan ölürler.'),
            ('negative', 'If he does not study, he fails.', 'Ders çalışmazsa kalır.'),
            ('negative', 'If we do not leave now, we are late.', 'Şimdi çıkmazsak geç kalırız.'),
            ('negative', 'If you don\'t sleep enough, you get tired.', 'Yeterince uyumazsan yorgun olursun.'),
            ('negative', 'Babies cry if they are not fed on time.', 'Bebekler zamanında beslenmezse ağlar.'),
            ('negative', 'If I don\'t drink water, I get headaches.', 'Su içmezsem başım ağrır.'),
            ('question', 'What happens if you press this button?', 'Bu tuşa basarsan ne olur?'),
            ('question', 'Does the alarm ring if someone opens the door?', 'Birisi kapıyı açarsa alarm çalar mı?'),
            ('question', 'If it is cold, do you wear a coat?', 'Hava soğuksa palto giyer misin?'),
            ('question', 'Do plants grow better if they get sunlight?', 'Bitkiler güneş alırsa daha iyi mi büyür?'),
            ('question', 'What do you do if you get lost?', 'Kaybolursan ne yaparsın?'),
            ('question', 'Does ice melt if you leave it in the sun?', 'Buzu güneşte bırakırsan erir mi?'),
        ],
    },
    {
        'slug': 'conditional-1',
        'name': 'First Conditional',
        'explanation': (
            'First Conditional, gelecekte gerçekleşmesi muhtemel, gerçekçi durumlar için kullanılır.\n\n'
            'NE ZAMAN KULLANILIR?\n'
            '• Gerçekçi gelecek olasılık: If it rains tomorrow, we will stay home.\n'
            '• Uyarılar ve planlar: If you don\'t hurry, you will miss the bus.\n'
            '• Söz verme / teklif: If you help me, I will help you.\n\n'
            'YAPI\n'
            '• If + Present Simple, will + V1\n'
            '    If you call me, I will answer.\n'
            '• Her iki sıralama da kullanılabilir:\n'
            '    I will answer if you call me.\n\n'
            'İPUÇLARI\n'
            '• "if" kısmında WILL KULLANILMAZ:\n'
            '    If it WILL rain ❌ → If it RAINS ✅\n'
            '• "will" yerine "may", "might", "can", "should" gibi modaller de kullanılabilir:\n'
            '    If you study, you may pass.\n'
            '• Virgül: "if" başta olduğunda virgül konur; sonda olduğunda genelde konmaz.'
        ),
        'examples': [
            ('positive', 'If it rains, I will stay home.', 'Yağmur yağarsa evde kalacağım.'),
            ('positive', 'If you study, you will pass.', 'Ders çalışırsan geçeceksin.'),
            ('positive', 'If she calls, I will answer.', 'O ararsa cevap veririm.'),
            ('positive', 'If we save enough money, we will buy a house.', 'Yeterince para biriktirirsek ev alırız.'),
            ('positive', 'If he arrives on time, we will start the meeting.', 'Zamanında gelirse toplantıyı başlatırız.'),
            ('positive', 'If you finish your work, we will watch a movie.', 'İşini bitirirsen film izleriz.'),
            ('negative', 'If you do not hurry, you will miss the bus.', 'Acele etmezsen otobüsü kaçırırsın.'),
            ('negative', 'If he does not apologize, I will not talk to him.', 'Özür dilemezse onunla konuşmam.'),
            ('negative', 'If we do not leave now, we will not arrive on time.', 'Şimdi gitmezsek zamanında varamayız.'),
            ('negative', 'If she doesn\'t practice, she won\'t improve.', 'Pratik yapmazsa gelişmeyecek.'),
            ('negative', 'If it doesn\'t stop raining, we won\'t go out.', 'Yağmur durmazsa dışarı çıkmayacağız.'),
            ('negative', 'If you don\'t water the plant, it will die.', 'Bitkiyi sulamazsan ölecek.'),
            ('question', 'What will you do if it rains?', 'Yağmur yağarsa ne yapacaksın?'),
            ('question', 'Will she come if we invite her?', 'Onu çağırırsak gelir mi?'),
            ('question', 'If I help you, will you help me?', 'Sana yardım edersem bana yardım eder misin?'),
            ('question', 'What will happen if we are late?', 'Geç kalırsak ne olur?'),
            ('question', 'Will you be angry if I cancel the plans?', 'Planları iptal edersem kızar mısın?'),
            ('question', 'If the weather is bad, will the match be postponed?', 'Hava kötü olursa maç ertelenecek mi?'),
        ],
    },
    {
        'slug': 'conditional-2',
        'name': 'Second Conditional',
        'explanation': (
            'Second Conditional, şu an veya gelecekte gerçek olmayan, hayali ya da çok uzak ihtimal durumlar için kullanılır.\n\n'
            'NE ZAMAN KULLANILIR?\n'
            '• Hayal / imkânsız durum: If I had wings, I would fly.\n'
            '• Uzak ihtimal: If I won the lottery, I would buy an island.\n'
            '• Tavsiye: If I were you, I would apologize.\n\n'
            'YAPI\n'
            '• If + Past Simple, would + V1\n'
            '    If he came, he would see the show.\n'
            '• "I / he / she / it" ile genelde "were" kullanılır (daha resmi):\n'
            '    If I were rich... / If she were here...\n'
            '• Olumsuz: If I didn\'t have work, I wouldn\'t stay.\n\n'
            'İPUÇLARI\n'
            '• "if" tarafında "would" KULLANILMAZ: If I WOULD have ❌ → If I HAD ✅\n'
            '• "would" yerine "could" veya "might" de kullanılabilir:\n'
            '    If I had more time, I could travel more.\n'
            '• "If I were you" tavsiye vermenin kibar yoludur.'
        ),
        'examples': [
            ('positive', 'If I had money, I would travel the world.', 'Param olsa dünyayı gezerdim.'),
            ('positive', 'If she knew him, she would call.', 'Onu tanısaydı arardı.'),
            ('positive', 'If I were you, I would apologize.', 'Senin yerinde olsam özür dilerdim.'),
            ('positive', 'If we lived closer, we would visit you more often.', 'Daha yakın yaşasak seni daha sık ziyaret ederdik.'),
            ('positive', 'If I could speak Japanese, I would move to Tokyo.', 'Japonca konuşabilsem Tokyo\'ya taşınırdım.'),
            ('positive', 'If he had a car, he would drive us.', 'Arabası olsa bizi götürürdü.'),
            ('negative', 'If I were rich, I would not work.', 'Zengin olsam çalışmazdım.'),
            ('negative', 'If he knew the truth, he would not stay.', 'Gerçeği bilse kalmazdı.'),
            ('negative', 'If we had time, we would not rush.', 'Zamanımız olsa acele etmezdik.'),
            ('negative', 'If she didn\'t have a dog, she wouldn\'t go out so much.', 'Köpeği olmasa bu kadar sık dışarı çıkmazdı.'),
            ('negative', 'If I had a garden, I wouldn\'t live in an apartment.', 'Bahçem olsa apartmanda yaşamazdım.'),
            ('negative', 'If they weren\'t so busy, they would visit more often.', 'Bu kadar meşgul olmasalar daha sık ziyaret ederlerdi.'),
            ('question', 'What would you do if you won the lottery?', 'Piyangoyu kazansan ne yapardın?'),
            ('question', 'Would you help me if I asked?', 'İstesem bana yardım eder miydin?'),
            ('question', 'If you could fly, where would you go?', 'Uçabilseydin nereye giderdin?'),
            ('question', 'If you had one wish, what would it be?', 'Bir dileğin olsa ne olurdu?'),
            ('question', 'Would she stay if we offered her a better salary?', 'Daha iyi maaş teklif etsek kalır mıydı?'),
            ('question', 'If you were president, what would you change?', 'Cumhurbaşkanı olsan neyi değiştirirdin?'),
        ],
    },
    {
        'slug': 'conditional-3',
        'name': 'Third Conditional',
        'explanation': (
            'Third Conditional, geçmişte gerçekleşmemiş hayali durumları ve sık sık pişmanlıkları anlatmak için kullanılır.\n\n'
            'NE ZAMAN KULLANILIR?\n'
            '• Geçmiş pişmanlık: If I had studied harder, I would have passed.\n'
            '• Hayali geçmiş sonuç: If he had left earlier, he would have caught the train.\n'
            '• Eleştiri: If you had told me, I would have helped.\n\n'
            'YAPI\n'
            '• If + Past Perfect, would have + V3\n'
            '    If I had known, I would have come.\n'
            '• Olumsuz: If you hadn\'t called me, I wouldn\'t have found out.\n\n'
            'İPUÇLARI\n'
            '• "if" tarafında WOULD HAVE yazma: If I WOULD have known ❌ → If I HAD known ✅\n'
            '• "would have" yerine "could have", "might have" de kullanılabilir:\n'
            '    If we had left earlier, we could have arrived on time.\n'
            '• Bu zaman yalnızca geçmişle ilgili "eğer öyle olsaydı" durumlarında kullanılır. Gerçek olmamış, olamaz.'
        ),
        'examples': [
            ('positive', 'If I had studied, I would have passed.', 'Ders çalışsaydım geçerdim.'),
            ('positive', 'If she had called me, I would have helped.', 'Beni arasaydı yardım ederdim.'),
            ('positive', 'If they had left earlier, they would have caught the train.', 'Daha erken çıksalardı treni yakalarlardı.'),
            ('positive', 'If we had taken a map, we would have found the place.', 'Harita alsaydık yeri bulurduk.'),
            ('positive', 'If you had come to the party, you would have met her.', 'Partiye gelseydin onunla tanışırdın.'),
            ('positive', 'If the team had played better, they would have won the cup.', 'Takım daha iyi oynasaydı kupayı kazanırdı.'),
            ('negative', 'If you had not helped me, I would not have succeeded.', 'Bana yardım etmeseydin başaramazdım.'),
            ('negative', 'If it had not rained, we would not have stayed home.', 'Yağmur yağmasaydı evde kalmazdık.'),
            ('negative', 'If he had listened, he would not have made the mistake.', 'Dinleseydi bu hatayı yapmazdı.'),
            ('negative', 'If they hadn\'t been late, we wouldn\'t have missed the show.', 'Geç kalmasalardı gösteriyi kaçırmazdık.'),
            ('negative', 'If I hadn\'t forgotten my umbrella, I wouldn\'t have gotten wet.', 'Şemsiyemi unutmasaydım ıslanmazdım.'),
            ('negative', 'If she hadn\'t moved abroad, we wouldn\'t have lost touch.', 'Yurt dışına taşınmasaydı iletişimi kaybetmezdik.'),
            ('question', 'What would you have done if you had known?', 'Bilseydin ne yapardın?'),
            ('question', 'Would you have come if we had invited you?', 'Seni çağırsaydık gelir miydin?'),
            ('question', 'If she had asked, would you have answered?', 'Sorsaydı cevap verir miydin?'),
            ('question', 'What would have happened if we had missed the flight?', 'Uçağı kaçırsaydık ne olurdu?'),
            ('question', 'Would he have stayed if the job had been better?', 'İş daha iyi olsaydı kalır mıydı?'),
            ('question', 'If the weather had been nice, would you have gone swimming?', 'Hava güzel olsaydı yüzmeye gider miydin?'),
        ],
    },
    {
        'slug': 'passive-voice',
        'name': 'Passive Voice',
        'explanation': (
            'Passive Voice (Edilgen Çatı), eylemi yapandan ziyade eylemin kendisine ya da eylemden etkilenen nesneye odaklanmak istendiğinde kullanılır.\n\n'
            'NE ZAMAN KULLANILIR?\n'
            '• Eylemi yapan belli değil ya da önemsiz: The window was broken.\n'
            '• Nesne / eylemin etkisi daha önemli: The project was completed last week.\n'
            '• Bilimsel ve resmi anlatımlarda çok kullanılır: Water is heated to 100°C.\n\n'
            'YAPI (tüm zamanlarda): Özne + be (o zamanın hâli) + V3\n'
            '• Present Simple: is/are + V3 → The room is cleaned every day.\n'
            '• Past Simple: was/were + V3 → The letter was sent.\n'
            '• Present Perfect: has/have been + V3 → The door has been repaired.\n'
            '• Future: will be + V3 → The results will be announced.\n'
            '• Modal: can/should be + V3 → The problem can be solved.\n\n'
            'İPUÇLARI\n'
            '• Eylemi yapan önemliyse "by" ile belirtilir: The book was written by George Orwell.\n'
            '• Geçişsiz fiiller (go, arrive, sleep...) passive\'e çevrilmez.\n'
            '• Türkçedeki "-miş", "-di" ve "-ilir" eklerine benzer bir yapıdır.'
        ),
        'examples': [
            ('positive', 'The cake was eaten.', 'Kek yendi.'),
            ('positive', 'The house was built in 1990.', 'Ev 1990\'da inşa edildi.'),
            ('positive', 'English is spoken here.', 'Burada İngilizce konuşulur.'),
            ('positive', 'The report has been finished.', 'Rapor bitirildi.'),
            ('positive', 'This song was written by a famous artist.', 'Bu şarkı ünlü bir sanatçı tarafından yazıldı.'),
            ('positive', 'The streets are cleaned every morning.', 'Sokaklar her sabah temizlenir.'),
            ('negative', 'The letter was not sent.', 'Mektup gönderilmedi.'),
            ('negative', 'The room is not cleaned every day.', 'Oda her gün temizlenmez.'),
            ('negative', 'The window has not been fixed.', 'Pencere tamir edilmedi.'),
            ('negative', 'These rules are not followed by everyone.', 'Bu kurallara herkes uymuyor.'),
            ('negative', 'The package was not delivered on time.', 'Paket zamanında teslim edilmedi.'),
            ('negative', 'The problem has not been solved yet.', 'Sorun henüz çözülmedi.'),
            ('question', 'Was the email sent?', 'E-posta gönderildi mi?'),
            ('question', 'Is this book read by many people?', 'Bu kitap çok kişi tarafından okunur mu?'),
            ('question', 'When was it invented?', 'Ne zaman icat edildi?'),
            ('question', 'Has the homework been checked?', 'Ödev kontrol edildi mi?'),
            ('question', 'Will the decision be made today?', 'Karar bugün verilecek mi?'),
            ('question', 'Can the issue be fixed quickly?', 'Sorun hızlıca çözülebilir mi?'),
        ],
    },
    {
        'slug': 'reported-speech',
        'name': 'Reported Speech',
        'explanation': (
            'Reported Speech (Dolaylı Anlatım), başkasının söylediklerini doğrudan alıntı yapmadan aktarmak için kullanılır. Zamanlar genellikle bir adım geri kayar.\n\n'
            'ZAMAN GERİ KAYMALARI\n'
            '• Present Simple → Past Simple\n'
            '• Present Continuous → Past Continuous\n'
            '• Present Perfect → Past Perfect\n'
            '• Past Simple → Past Perfect\n'
            '• will → would\n'
            '• can → could\n'
            '• must → had to\n\n'
            'ZAMİR VE ZAMAN KELİMELERİ DEĞİŞİR\n'
            '• I → he/she, we → they, my → his/her\n'
            '• now → then, today → that day, yesterday → the day before, tomorrow → the next day\n\n'
            'YAPI\n'
            '• Olumlu cümle: He said (that) + dönüştürülmüş cümle.\n'
            '    "I am tired." → He said (that) he was tired.\n'
            '• Soru: He asked + soru sözcüğü / if + dönüştürülmüş cümle. (YARDIMCI FİİL GİDER, düz cümle yapısı kurulur!)\n'
            '    "Where do you live?" → He asked where I lived.\n'
            '    "Are you OK?" → He asked if I was OK.\n\n'
            'İPUÇLARI\n'
            '• "say" nesne almadan, "tell" nesne alarak kullanılır: He said (to me)... / He told me...\n'
            '• Evrensel gerçekler geri kaymayabilir: He said the Earth revolves around the Sun.'
        ),
        'examples': [
            ('positive', 'She said she was tired.', 'Yorgun olduğunu söyledi.'),
            ('positive', 'He told me he had finished the work.', 'Bana işi bitirdiğini söyledi.'),
            ('positive', 'They said they would come.', 'Geleceklerini söylediler.'),
            ('positive', 'Maria said she loved chocolate cake.', 'Maria çikolatalı kek sevdiğini söyledi.'),
            ('positive', 'The doctor said I had to rest.', 'Doktor dinlenmem gerektiğini söyledi.'),
            ('positive', 'He said he had been studying all day.', 'Bütün gün çalıştığını söyledi.'),
            ('negative', 'He said he did not know.', 'Bilmediğini söyledi.'),
            ('negative', 'She told me she had not seen him.', 'Onu görmediğini söyledi.'),
            ('negative', 'They said they were not hungry.', 'Aç olmadıklarını söylediler.'),
            ('negative', 'Anna said she wouldn\'t attend the party.', 'Anna partiye katılmayacağını söyledi.'),
            ('negative', 'My friend told me he hadn\'t finished the assignment.', 'Arkadaşım ödevi bitirmediğini söyledi.'),
            ('negative', 'The teacher said we must not talk during the exam.', 'Öğretmen sınavda konuşmamamız gerektiğini söyledi.'),
            ('question', 'He asked me where I lived.', 'Bana nerede yaşadığımı sordu.'),
            ('question', 'She asked if I was ready.', 'Hazır olup olmadığımı sordu.'),
            ('question', 'They asked when the meeting would start.', 'Toplantının ne zaman başlayacağını sordular.'),
            ('question', 'I asked him why he was late.', 'Ona neden geç kaldığını sordum.'),
            ('question', 'She wanted to know if I had seen her keys.', 'Anahtarlarını görüp görmediğimi öğrenmek istedi.'),
            ('question', 'He asked me how long I had been waiting.', 'Ne kadar süredir beklediğimi sordu.'),
        ],
    },
    {
        'slug': 'comparatives-superlatives',
        'name': 'Comparatives & Superlatives',
        'explanation': (
            'Comparatives (karşılaştırma) ve Superlatives (üstünlük), iki veya daha fazla şeyi karşılaştırmak için kullanılır.\n\n'
            'KURALLAR\n'
            '• 1 heceli sıfatlar → -er / -est: tall → taller → the tallest, fast → faster → the fastest\n'
            '• "y" ile biten 2 heceli → y düşer, -ier / -iest: happy → happier → the happiest\n'
            '• 2+ heceli sıfatlar → more / the most: beautiful → more beautiful → the most beautiful\n'
            '• Düzensizler: good → better → the best, bad → worse → the worst, far → farther/further → the farthest\n\n'
            'YAPI\n'
            '• Comparative: X + is/are + sıfat-er (veya more + sıfat) + than + Y\n'
            '    This car is faster than that one.\n'
            '    This movie is more interesting than the book.\n'
            '• Superlative: X + is/are + the + sıfat-est (veya the most + sıfat) + grup\n'
            '    She is the tallest in the class.\n'
            '    This is the most expensive watch in the store.\n\n'
            'EŞİTLİK VE EŞİTSİZLİK\n'
            '• as + sıfat + as → eşit karşılaştırma: He is as tall as his brother.\n'
            '• not as + sıfat + as → daha az: This test is not as hard as the previous one.\n\n'
            'İPUÇLARI\n'
            '• Superlative\'den önce genellikle "the" gelir.\n'
            '• Hem -er hem more kullanma: more taller ❌ → taller ✅'
        ),
        'examples': [
            ('positive', 'This book is better than that one.', 'Bu kitap ondan daha iyi.'),
            ('positive', 'She is the tallest in the class.', 'Sınıftaki en uzun boylu o.'),
            ('positive', 'Today is hotter than yesterday.', 'Bugün dünden daha sıcak.'),
            ('positive', 'Mount Everest is the highest mountain in the world.', 'Everest Dağı dünyanın en yüksek dağıdır.'),
            ('positive', 'My new phone is faster than my old one.', 'Yeni telefonum eskisinden daha hızlı.'),
            ('positive', 'This is the most delicious meal I have ever had.', 'Bu yediğim en lezzetli yemek.'),
            ('negative', 'This is not as expensive as I thought.', 'Bu düşündüğüm kadar pahalı değil.'),
            ('negative', 'He is not the fastest runner.', 'O en hızlı koşucu değil.'),
            ('negative', 'That movie was not as good as this one.', 'O film bunun kadar iyi değildi.'),
            ('negative', 'The coffee here is not as strong as I like it.', 'Buradaki kahve sevdiğim kadar sert değil.'),
            ('negative', 'English is not as difficult as Chinese for me.', 'Bana göre İngilizce Çince kadar zor değil.'),
            ('negative', 'This is not the cheapest option on the menu.', 'Bu menüdeki en ucuz seçenek değil.'),
            ('question', 'Which is the most interesting?', 'En ilginç olan hangisi?'),
            ('question', 'Is it colder today than yesterday?', 'Bugün dünden daha mı soğuk?'),
            ('question', 'Who is taller, you or your brother?', 'Kim daha uzun, sen mi kardeşin mi?'),
            ('question', 'Which country is the largest in Europe?', 'Avrupa\'nın en büyük ülkesi hangisi?'),
            ('question', 'Is this restaurant better than the one downtown?', 'Bu restoran şehir merkezindekinden daha mı iyi?'),
            ('question', 'What is the most beautiful place you have visited?', 'Ziyaret ettiğin en güzel yer neresi?'),
        ],
    },
]


class Command(BaseCommand):
    help = 'Hazır gramer konularını ve örneklerini veritabanına yükler (idempotent — örnekler her çalıştırmada senkronize edilir).'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true', help='Önce tüm konuları sil.')

    def handle(self, *args, **opts):
        if opts.get('reset'):
            Topic.objects.all().delete()
            self.stdout.write(self.style.WARNING('Mevcut konular silindi.'))

        created_topics = 0
        total_examples = 0
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
                if was_created:
                    created_topics += 1
                else:
                    topic.name = t['name']
                    topic.explanation = t['explanation']
                    topic.order = order
                    topic.save()

                topic.examples.all().delete()
                for kind, en, tr in t['examples']:
                    TopicExample.objects.create(
                        topic=topic, kind=kind, sentence_en=en, sentence_tr=tr,
                    )
                    total_examples += 1

        self.stdout.write(self.style.SUCCESS(
            f'Bitti. Yeni konu: {created_topics}, toplam senkronize örnek: {total_examples}.'
        ))
