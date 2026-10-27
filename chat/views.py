from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Max, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import MessageForm
from .models import Conversation, Message

User = get_user_model()


@login_required
def inbox(request):
    conversations_qs = (
        Conversation.objects
        .filter(participants=request.user)
        .annotate(
            last_activity=Max("messages__created_at"),
            unread_count=Count(
                "messages",
                filter=Q(messages__is_read=False)
                & ~Q(messages__sender=request.user),
            ),
        )
        .prefetch_related("participants")
        .order_by("-last_activity", "-updated_at")
    )

    query = request.GET.get("q", "").strip()
    user_results = None

    if query:
        # Filter existing conversations
        conversations_qs = conversations_qs.filter(
            Q(subject__icontains=query)
            | Q(participants__username__icontains=query)
            | Q(participants__first_name__icontains=query)
            | Q(participants__last_name__icontains=query)
        ).distinct()

        # Search for NEW users to start a conversation with
        user_results = (
            User.objects.filter(
                Q(username__icontains=query)
                | Q(first_name__icontains=query)
                | Q(last_name__icontains=query)
            )
            .exclude(pk=request.user.pk)
            .exclude(pk__in=request.user.chat_conversations.values_list("participants__pk", flat=True))
            .distinct()[:5]
        )

    # Convert to list so we can attach dynamic attributes
    conversations = list(conversations_qs)

    # Attach the 'other_user' to each conversation for the template
    for conv in conversations:
        conv.other_user = conv.other_participant(request.user)

    return render(
        request,
        "chat/inbox.html",
        {
            "conversations": conversations,
            "query": query,
            "user_results": user_results,
        },
    )


@login_required
def start_conversation(request, username):
    recipient = get_object_or_404(User, username=username)

    if recipient.pk == request.user.pk:
        messages.error(request, "You cannot start a conversation with yourself.")
        return redirect("chat:inbox")

    existing = (
        Conversation.objects
        .filter(participants=request.user)
        .filter(participants=recipient)
        .annotate(participant_count=Count("participants", distinct=True))
        .filter(participant_count=2)
        .first()
    )

    if existing:
        return redirect("chat:conversation", pk=existing.pk)

    conversation = Conversation.objects.create()
    conversation.participants.add(request.user, recipient)

    return redirect("chat:conversation", pk=conversation.pk)


@login_required
def conversation_detail(request, pk):
    conversation = get_object_or_404(
        Conversation.objects.prefetch_related("participants"),
        pk=pk,
        participants=request.user,
    )

    if request.method == "POST":
        form = MessageForm(request.POST, request.FILES)

        if form.is_valid():
            message = form.save(commit=False)
            message.conversation = conversation
            message.sender = request.user
            message.save()

            conversation.save(update_fields=["updated_at"])

            return redirect("chat:conversation", pk=conversation.pk)
    else:
        form = MessageForm()

    conversation.messages.exclude(
        sender=request.user
    ).filter(
        is_read=False
    ).update(is_read=True)

    chat_messages = (
        conversation.messages
        .select_related("sender")
        .order_by("created_at")
    )

    recipient = conversation.other_participant(request.user)

    return render(
        request,
        "chat/conversation.html",
        {
            "conversation": conversation,
            "chat_messages": chat_messages,
            "form": form,
            "recipient": recipient,
        },
    )


@login_required
@require_POST
def delete_message(request, pk):
    message = get_object_or_404(
        Message.objects.select_related("conversation"),
        pk=pk,
        sender=request.user,
        conversation__participants=request.user,
    )

    conversation_id = message.conversation_id
    message.delete()

    messages.success(request, "Message deleted.")
    return redirect("chat:conversation", pk=conversation_id)