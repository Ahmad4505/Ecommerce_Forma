from rest_framework.throttling import UserRateThrottle

class CheckoutThrottle(UserRateThrottle):
    scope='checkout'

class PaymentThrottle(UserRateThrottle):
    scope='payment'

class UploadThrottle(UserRateThrottle):
    scope='upload'
