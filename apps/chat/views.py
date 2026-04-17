from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from services import ai
from .models import ChatConversation, ChatMessage


MAX_HISTORY = 20
DEFAULT_TITLE = 'New chat'


def _get_or_create_conversation(request) -> ChatConversation:
    conv_id = request.session.get('chat_conv_id')
    if conv_id:
        conv = ChatConversation.objects.filter(pk=conv_id, user=request.user).first()
        if conv:
            return conv
    conv = ChatConversation.objects.create(user=request.user)
    request.session['chat_conv_id'] = conv.pk
    return conv


def _user_conversations(user):
    return ChatConversation.objects.filter(user=user).order_by('-updated_at')


@login_required
def chat_page(request):
    conv = _get_or_create_conversation(request)
    return render(request, 'chat/page.html', {
        'conversation': conv,
        'messages_list': conv.messages.all(),
        'conversations': _user_conversations(request.user),
    })


@login_required
def send(request):
    if request.method != 'POST':
        return redirect('chat:page')

    text = request.POST.get('message', '').strip()
    if not text:
        return redirect('chat:page')

    conv = _get_or_create_conversation(request)
    was_empty = conv.title == DEFAULT_TITLE and not conv.messages.exists()
    ChatMessage.objects.create(conversation=conv, role=ChatMessage.USER, content=text)

    if was_empty:
        snippet = text.strip().splitlines()[0][:60].rstrip()
        if snippet:
            conv.title = snippet
            conv.save(update_fields=['title'])

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


@login_required
def open_conversation(request, pk):
    conv = get_object_or_404(ChatConversation, pk=pk, user=request.user)
    request.session['chat_conv_id'] = conv.pk
    return redirect('chat:page')


@login_required
@require_POST
def rename_conversation(request, pk):
    conv = get_object_or_404(ChatConversation, pk=pk, user=request.user)
    new_title = (request.POST.get('title') or '').strip()[:120]
    if not new_title:
        messages.error(request, _('Başlık boş olamaz.'))
    else:
        conv.title = new_title
        conv.save(update_fields=['title'])
        messages.success(request, _('Başlık güncellendi.'))
    return redirect('chat:page')


@login_required
@require_POST
def delete_conversation(request, pk):
    conv = get_object_or_404(ChatConversation, pk=pk, user=request.user)
    was_active = request.session.get('chat_conv_id') == conv.pk
    conv.delete()
    if was_active:
        request.session.pop('chat_conv_id', None)
    messages.success(request, _('Sohbet silindi.'))
    return redirect('chat:page')
