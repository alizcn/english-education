from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.utils.translation import gettext as _

from services import ai
from .models import ChatConversation, ChatMessage


MAX_HISTORY = 20


def _get_or_create_conversation(request) -> ChatConversation:
    conv_id = request.session.get('chat_conv_id')
    if conv_id:
        conv = ChatConversation.objects.filter(pk=conv_id, user=request.user).first()
        if conv:
            return conv
    conv = ChatConversation.objects.create(user=request.user)
    request.session['chat_conv_id'] = conv.pk
    return conv


@login_required
def chat_page(request):
    conv = _get_or_create_conversation(request)
    return render(request, 'chat/page.html', {
        'conversation': conv,
        'messages_list': conv.messages.all(),
    })


@login_required
def send(request):
    if request.method != 'POST':
        return redirect('chat:page')

    text = request.POST.get('message', '').strip()
    if not text:
        return redirect('chat:page')

    conv = _get_or_create_conversation(request)
    ChatMessage.objects.create(conversation=conv, role=ChatMessage.USER, content=text)

    history = list(conv.messages.order_by('-created_at')[:MAX_HISTORY])
    history.reverse()
    api_messages = [{'role': m.role, 'content': m.content} for m in history]

    try:
        reply = ai.chat(api_messages)
    except Exception as e:
        messages.error(request, _('AI hata: %(error)s') % {'error': e})
        return redirect('chat:page')

    reply = (reply or '').strip()
    if not reply:
        messages.error(request, _('AI boş yanıt döndü. Tekrar dene.'))
        return redirect('chat:page')

    ChatMessage.objects.create(conversation=conv, role=ChatMessage.ASSISTANT, content=reply)
    conv.save()
    return redirect('chat:page')


@login_required
def new_conversation(request):
    request.session.pop('chat_conv_id', None)
    messages.info(request, _('Yeni sohbet başlatıldı.'))
    return redirect('chat:page')
