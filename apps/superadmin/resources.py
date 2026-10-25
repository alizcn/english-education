"""All resources registered with the superadmin.

Importing this module side-effects the registry. The app's AppConfig.ready()
imports it once at startup.
"""
from django.contrib.auth import get_user_model

from apps.accounts.models import UserConsent, UserCourse
from apps.quizzes.models import QuizTemplate, QuizSession, QuizQuestion
from apps.interviews.models import InterviewSession
from apps.topics.models import (
    Topic, TopicCompletion, TopicExample, TopicExplanation,
)
from apps.vocabulary.models import Word
from apps.wordbank.models import BankProgress, BankWord, BankWordTranslation
from apps.chat.models import ChatConversation, ChatMessage

from .registry import Resource, register


User = get_user_model()


# ===================== Kullanıcılar =====================

@register('users')
class UserResource(Resource):
    model = User
    label = 'Kullanıcılar'
    label_singular = 'Kullanıcı'
    icon = '👥'
    section = 'Kullanıcılar'
    list_columns = (
        ('id', '#'),
        ('username', 'Kullanıcı Adı'),
        ('email', 'E-posta'),
        ('is_superuser', 'Süper'),
        ('is_staff', 'Personel'),
        ('is_active', 'Aktif'),
        ('date_joined', 'Kayıt'),
    )
    search_fields = ('username', 'email', 'first_name', 'last_name')
    filters = (
        ('is_superuser', 'Süper Kullanıcı'),
        ('is_staff', 'Personel'),
        ('is_active', 'Aktif'),
    )
    form_fields = ('username', 'email', 'first_name', 'last_name',
                   'is_active', 'is_staff', 'is_superuser')
    order_by = ('-date_joined',)
    detail_extra = (
        ('quiz_session_count', 'Quiz Oturumu'),
        ('interview_count', 'Mülakat Sayısı'),
        ('word_count', 'Kişisel Kelime'),
    )

    def quiz_session_count(self, obj):
        return obj.quiz_sessions.count()

    def interview_count(self, obj):
        return obj.interview_sessions.count()

    def word_count(self, obj):
        return obj.words.count()


@register('user-consents')
class UserConsentResource(Resource):
    model = UserConsent
    label = 'KVKK Onayları'
    label_singular = 'Onay'
    icon = '✅'
    section = 'Kullanıcılar'
    list_columns = (
        ('id', '#'),
        ('user', 'Kullanıcı'),
        ('kind', 'Tür'),
        ('accepted_at', 'Onay Zamanı'),
        ('ip_address', 'IP'),
    )
    search_fields = ('user__username', 'user__email', 'ip_address')
    filters = (('kind', 'Tür'),)
    select_related = ('user',)
    order_by = ('-accepted_at',)


@register('user-courses')
class UserCourseResource(Resource):
    model = UserCourse
    label = 'Kurslar'
    label_singular = 'Kurs'
    icon = '🎯'
    section = 'Kullanıcılar'
    list_columns = (
        ('id', '#'),
        ('user', 'Kullanıcı'),
        ('target_language', 'Öğrenilen'),
        ('native_language', 'Anlatım'),
        ('current_level', 'Seviye'),
        ('score', 'Skor'),
        ('is_active', 'Aktif'),
        ('updated_at', 'Güncelleme'),
    )
    search_fields = ('user__username', 'user__email')
    filters = (
        ('target_language', 'Öğrenilen dil'),
        ('native_language', 'Anlatım dili'),
        ('current_level', 'Seviye'),
        ('is_active', 'Aktif'),
    )
    select_related = ('user',)
    order_by = ('-updated_at',)


# ===================== İçerik =====================

@register('topics')
class TopicResource(Resource):
    model = Topic
    label = 'Konular'
    label_singular = 'Konu'
    icon = '📚'
    section = 'İçerik'
    list_columns = (
        ('id', '#'),
        ('language', 'Dil'),
        ('name', 'Ad'),
        ('slug', 'Slug'),
        ('order', 'Sıra'),
        ('explanation_languages', 'Anlatım'),
        ('created_at', 'Oluşturma'),
    )
    search_fields = ('name', 'slug')
    filters = (('language', 'Hedef dil'),)
    prefetch_related = ('explanations',)
    order_by = ('language', 'order', 'name')

    def explanation_languages(self, obj):
        return ', '.join(sorted(e.language for e in obj.explanations.all())) or '—'


@register('topic-examples')
class TopicExampleResource(Resource):
    model = TopicExample
    label = 'Konu Örnekleri'
    label_singular = 'Örnek'
    icon = '💡'
    section = 'İçerik'
    list_columns = (
        ('id', '#'),
        ('topic', 'Konu'),
        ('kind', 'Tür'),
        ('order', 'Sıra'),
        ('sentence', 'Cümle'),
        ('translation_languages', 'Çeviriler'),
    )
    search_fields = ('topic__name', 'sentence')
    filters = (('topic', 'Konu'), ('kind', 'Tür'))
    select_related = ('topic',)
    order_by = ('topic', 'kind', 'order')

    def translation_languages(self, obj):
        data = obj.translations if isinstance(obj.translations, dict) else {}
        return ', '.join(sorted(k for k, v in data.items() if v)) or '—'


@register('quiz-templates')
class QuizTemplateResource(Resource):
    model = QuizTemplate
    label = 'Quiz Şablonları'
    label_singular = 'Şablon'
    icon = '📝'
    section = 'İçerik'
    list_columns = (
        ('id', '#'),
        ('name', 'Ad'),
        ('kind', 'Tür'),
        ('target_language', 'Öğrenilen'),
        ('native_language', 'Anlatım'),
        ('topic', 'Konu'),
        ('user', 'Sahip'),
        ('question_count', 'Soru'),
        ('created_at', 'Oluşturma'),
    )
    search_fields = ('name', 'user__username', 'topic__name')
    filters = (
        ('kind', 'Tür'), ('target_language', 'Öğrenilen dil'),
        ('native_language', 'Anlatım dili'), ('topic', 'Konu'),
    )
    select_related = ('user', 'topic')
    order_by = ('-created_at',)

    def question_count(self, obj):
        try:
            return len(obj.questions_data or [])
        except Exception:
            return 0


@register('bank-words')
class BankWordResource(Resource):
    model = BankWord
    label = 'Kelime Bankası'
    label_singular = 'Kelime'
    icon = '📖'
    section = 'İçerik'
    list_columns = (
        ('id', '#'),
        ('language', 'Dil'),
        ('level', 'Seviye'),
        ('rank', 'Sıra'),
        ('term', 'Terim'),
        ('meanings', 'Anlamlar'),
        ('part_of_speech', 'PoS'),
    )
    search_fields = ('term', 'translations__meaning')
    filters = (
        ('language', 'Hedef dil'), ('level', 'Seviye'),
        ('part_of_speech', 'PoS'),
    )
    prefetch_related = ('translations',)
    order_by = ('language', 'level', 'rank')

    def meanings(self, obj):
        # Hangi dillerde anlam var — içerik üretimini gözden geçirirken
        # eksikleri görmenin en hızlı yolu.
        parts = [
            f'{t.language}: {t.meaning[:40]}'
            for t in sorted(obj.translations.all(), key=lambda x: x.language)
        ]
        return ' | '.join(parts) or '—'


@register('bank-word-translations')
class BankWordTranslationResource(Resource):
    model = BankWordTranslation
    label = 'Kelime Çevirileri'
    label_singular = 'Çeviri'
    icon = '🌐'
    section = 'İçerik'
    list_columns = (
        ('id', '#'),
        ('word', 'Terim'),
        ('language', 'Dil'),
        ('meaning', 'Anlam'),
        ('example_translation', 'Örnek çevirisi'),
    )
    search_fields = ('meaning', 'word__term')
    filters = (
        ('language', 'Anlatım dili'),
        ('word__language', 'Hedef dil'),
        ('word__level', 'Seviye'),
    )
    select_related = ('word',)
    order_by = ('word__language', 'word__level', 'word__rank', 'language')


@register('topic-explanations')
class TopicExplanationResource(Resource):
    model = TopicExplanation
    label = 'Konu Anlatımları'
    label_singular = 'Anlatım'
    icon = '📄'
    section = 'İçerik'
    list_columns = (
        ('id', '#'),
        ('topic', 'Konu'),
        ('language', 'Dil'),
        ('length', 'Uzunluk'),
        ('updated_at', 'Güncelleme'),
    )
    search_fields = ('body', 'topic__name', 'topic__slug')
    filters = (('language', 'Anlatım dili'), ('topic__language', 'Hedef dil'))
    select_related = ('topic',)
    order_by = ('topic', 'language')

    def length(self, obj):
        return f'{len(obj.body or "")} krk'


# ===================== Aktivite =====================

@register('quiz-sessions')
class QuizSessionResource(Resource):
    model = QuizSession
    label = 'Quiz Oturumları'
    label_singular = 'Oturum'
    icon = '⚡'
    section = 'Aktivite'
    list_columns = (
        ('id', '#'),
        ('user', 'Kullanıcı'),
        ('kind', 'Tür'),
        ('topic', 'Konu'),
        ('total_questions', 'Soru'),
        ('correct_count', 'Doğru'),
        ('wrong_count', 'Yanlış'),
        ('started_at', 'Başlangıç'),
        ('finished_at', 'Bitiş'),
    )
    search_fields = ('user__username', 'topic__name')
    filters = (('kind', 'Tür'), ('topic', 'Konu'))
    select_related = ('user', 'topic', 'template')
    order_by = ('-started_at',)
    can_create = False


@register('quiz-questions')
class QuizQuestionResource(Resource):
    model = QuizQuestion
    label = 'Quiz Soruları'
    label_singular = 'Soru'
    icon = '❓'
    section = 'Aktivite'
    list_columns = (
        ('id', '#'),
        ('session', 'Oturum'),
        ('order', 'Sıra'),
        ('question_type', 'Tür'),
        ('prompt', 'Soru'),
        ('correct_answer', 'Doğru'),
        ('user_answer', 'Cevap'),
        ('is_correct', 'Doğru?'),
    )
    search_fields = ('prompt', 'correct_answer')
    filters = (('question_type', 'Tür'), ('is_correct', 'Sonuç'))
    select_related = ('session', 'word')
    order_by = ('-id',)
    can_create = False


@register('interviews')
class InterviewResource(Resource):
    model = InterviewSession
    label = 'Mülakatlar'
    label_singular = 'Mülakat'
    icon = '🎤'
    section = 'Aktivite'
    list_columns = (
        ('id', '#'),
        ('user', 'Kullanıcı'),
        ('source', 'Kaynak'),
        ('job_category', 'Pozisyon'),
        ('custom_title', 'Başlık'),
        ('question_count', 'Soru'),
        ('created_at', 'Tarih'),
    )
    search_fields = ('user__username', 'custom_title', 'job_category')
    filters = (('source', 'Kaynak'), ('job_category', 'Pozisyon'))
    select_related = ('user',)
    order_by = ('-created_at',)
    can_create = False

    def question_count(self, obj):
        try:
            return len(obj.questions_data or [])
        except Exception:
            return 0


@register('words')
class WordResource(Resource):
    model = Word
    label = 'Kişisel Kelimeler'
    label_singular = 'Kelime'
    icon = '🗂️'
    section = 'Aktivite'
    list_columns = (
        ('id', '#'),
        ('user', 'Kullanıcı'),
        ('target_language', 'Öğrenilen'),
        ('term', 'Terim'),
        ('meaning', 'Anlam'),
        ('mastered', 'Öğrenildi'),
        ('times_correct', '✓'),
        ('times_asked', '?'),
        ('created_at', 'Eklenme'),
    )
    search_fields = ('term', 'meaning', 'user__username')
    filters = (
        ('target_language', 'Öğrenilen dil'),
        ('native_language', 'Anlatım dili'),
        ('mastered', 'Öğrenildi'),
    )
    select_related = ('user',)
    order_by = ('-created_at',)


@register('bank-progress')
class BankProgressResource(Resource):
    model = BankProgress
    label = 'Bank İlerlemesi'
    label_singular = 'İlerleme'
    icon = '📈'
    section = 'Aktivite'
    list_columns = (
        ('id', '#'),
        ('user', 'Kullanıcı'),
        ('word', 'Kelime'),
        ('mastered', 'Öğrenildi'),
        ('correct_count', '✓'),
        ('wrong_count', '✗'),
        ('last_answered_at', 'Son Cevap'),
    )
    search_fields = ('user__username', 'word__term')
    filters = (
        ('mastered', 'Öğrenildi'),
        ('word__language', 'Hedef dil'),
        ('word__level', 'Seviye'),
    )
    select_related = ('user', 'word')
    order_by = ('-last_answered_at',)


@register('topic-completions')
class TopicCompletionResource(Resource):
    model = TopicCompletion
    label = 'Konu Tamamlamaları'
    label_singular = 'Tamamlama'
    icon = '🏁'
    section = 'Aktivite'
    list_columns = (
        ('id', '#'),
        ('user', 'Kullanıcı'),
        ('topic', 'Konu'),
        ('completed_at', 'Tarih'),
    )
    search_fields = ('user__username', 'topic__name')
    filters = (('topic', 'Konu'),)
    select_related = ('user', 'topic')
    order_by = ('-completed_at',)


@register('chat-conversations')
class ChatConversationResource(Resource):
    model = ChatConversation
    label = 'Chat Oturumları'
    label_singular = 'Sohbet'
    icon = '💬'
    section = 'Aktivite'
    list_columns = (
        ('id', '#'),
        ('user', 'Kullanıcı'),
        ('title', 'Başlık'),
        ('msg_count', 'Mesaj'),
        ('created_at', 'Oluşturma'),
        ('updated_at', 'Güncelleme'),
    )
    search_fields = ('user__username', 'title')
    select_related = ('user',)
    order_by = ('-updated_at',)
    can_create = False

    def msg_count(self, obj):
        return obj.messages.count() if hasattr(obj, 'messages') else ''


@register('chat-messages')
class ChatMessageResource(Resource):
    model = ChatMessage
    label = 'Chat Mesajları'
    label_singular = 'Mesaj'
    icon = '✉️'
    section = 'Aktivite'
    list_columns = (
        ('id', '#'),
        ('conversation', 'Oturum'),
        ('role', 'Rol'),
        ('content_preview', 'İçerik'),
        ('created_at', 'Tarih'),
    )
    search_fields = ('content', 'conversation__user__username')
    filters = (('role', 'Rol'),)
    select_related = ('conversation', 'conversation__user')
    order_by = ('-created_at',)
    can_create = False

    def content_preview(self, obj):
        s = obj.content or ''
        return (s[:100] + '…') if len(s) > 100 else s


# ===================== Sistem =====================

@register('audit-logs')
class AuditLogResource(Resource):
    from auditlog.models import LogEntry as _LogEntry
    model = _LogEntry
    label = 'Audit Log'
    label_singular = 'Log'
    icon = '🔍'
    section = 'Sistem'
    list_columns = (
        ('timestamp', 'Zaman'),
        ('actor', 'Kullanıcı'),
        ('content_type', 'Model'),
        ('object_repr', 'Nesne'),
        ('get_action_display', 'İşlem'),
        ('changes_short', 'Değişiklikler'),
        ('remote_addr', 'IP'),
    )
    search_fields = ('object_repr', 'actor__username', 'actor__email')
    order_by = ('-timestamp',)
    can_create = False
    can_edit = False
    select_related = ('content_type', 'actor')

    def get_action_display(self, obj):
        return obj.get_action_display()

    def changes_short(self, obj):
        try:
            changes = obj.changes
            if not changes:
                return ''
            keys = list(changes.keys())
            preview = ', '.join(keys[:3])
            return f'{preview} (+{len(keys)-3})' if len(keys) > 3 else preview
        except Exception:
            return ''
