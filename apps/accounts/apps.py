from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.accounts'

    def ready(self):
        from . import signals  # noqa: F401
        self._register_auditlog()

    def _register_auditlog(self):
        from auditlog.registry import auditlog
        from django.contrib.auth.models import User
        from apps.accounts.models import UserConsent, UserCourse
        from apps.vocabulary.models import Word
        from apps.topics.models import Topic
        from apps.quizzes.models import QuizTemplate
        from apps.interviews.models import InterviewSession
        from apps.chat.models import ChatConversation

        for model in [User, UserConsent, UserCourse, Word, Topic,
                      QuizTemplate, InterviewSession, ChatConversation]:
            auditlog.register(model)
