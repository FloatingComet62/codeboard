from rest_framework import serializers
from .models import User


class UserSerializer(serializers.ModelSerializer):
    has_leetcode = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'picture', 'has_leetcode']

    def get_has_leetcode(self, obj):
        return hasattr(obj, 'leetcode')
