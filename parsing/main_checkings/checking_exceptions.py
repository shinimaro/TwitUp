

class SubscriptionFailed(Exception):
    """Не выполнена подписка на аккаунт"""


class LikeFailed(Exception):
    """Не поставлен лайк на пост"""


class RetweetFailed(Exception):
    """Не выполнен ретвит поста"""


class CommentFailed(Exception):
    """Комментарий не найден"""
