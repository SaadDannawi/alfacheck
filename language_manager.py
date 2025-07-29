"""Language management system for Telegram Bot."""

import json
from typing import Dict, Optional
from dataclasses import dataclass
from enum import Enum

class Language(Enum):
    """Supported languages."""
    ENGLISH = "en"
    ARABIC = "ar"

@dataclass
class UserLanguagePreference:
    """User language preference."""
    user_id: int
    language: Language

class LanguageManager:
    """Manages language translations and user preferences."""
    
    def __init__(self):
        self.user_preferences: Dict[int, Language] = {}
        self.translations = self._load_translations()
    
    def _load_translations(self) -> Dict[str, Dict[str, str]]:
        """Load translation dictionaries."""
        return {
            # Bot Messages
            "welcome_title": {
                "en": "🔍 **Alfa Account Data Extraction Bot**",
                "ar": "🔍 **بوت استخراج بيانات حسابات ألفا**"
            },
            "status": {
                "en": "**Status:**",
                "ar": "**الحالة:**"
            },
            "admin": {
                "en": "👑 **ADMIN**",
                "ar": "👑 **مدير**"
            },
            "authorized": {
                "en": "✅ **AUTHORIZED**",
                "ar": "✅ **مخول**"
            },
            "access_restricted": {
                "en": "🔒 **Access Restricted**",
                "ar": "🔒 **الوصول مقيد**"
            },
            "access_denied": {
                "en": "🔒 **Access Denied**",
                "ar": "🔒 **تم رفض الوصول**"
            },
            "unauthorized_message": {
                "en": "This bot requires authorization to use.\nPlease contact an administrator to request access.",
                "ar": "هذا البوت يتطلب تخويل للاستخدام.\nيرجى الاتصال بالمدير لطلب الوصول."
            },
            "your_user_id": {
                "en": "Your User ID:",
                "ar": "معرف المستخدم الخاص بك:"
            },
            "provide_id_to_admin": {
                "en": "Provide this ID to the administrator for authorization.",
                "ar": "قدم هذا المعرف للمدير للحصول على التخويل."
            },
            "send_format_instruction": {
                "en": "Send me a list of account numbers with password in this format:",
                "ar": "أرسل لي قائمة بأرقام الحسابات مع كلمة المرور بهذا التنسيق:"
            },
            "instructions_title": {
                "en": "📝 **Instructions:**",
                "ar": "📝 **التعليمات:**"
            },
            "list_accounts": {
                "en": "• List account numbers (one per line)",
                "ar": "• اكتب أرقام الحسابات (رقم واحد في كل سطر)"
            },
            "password_last_line": {
                "en": "• Put the password on the last line",
                "ar": "• ضع كلمة المرور في السطر الأخير"
            },
            "maximum_accounts": {
                "en": "• Maximum {max_accounts} accounts per request",
                "ar": "• الحد الأقصى {max_accounts} حساب لكل طلب"
            },
            "process_and_send": {
                "en": "• I'll process accounts and send results",
                "ar": "• سأقوم بمعالجة الحسابات وإرسال النتائج"
            },
            "receive_csv": {
                "en": "• Finally, you'll receive a CSV file with all results",
                "ar": "• أخيراً، ستحصل على ملف CSV يحتوي على جميع النتائج"
            },
            "batch_processing": {
                "en": "⚡ **Batch Processing:**",
                "ar": "⚡ **المعالجة المجمعة:**"
            },
            "batch_size": {
                "en": "📦 **Batch Size:**",
                "ar": "📦 **حجم المجموعة:**"
            },
            "max_workers": {
                "en": "🔧 **Max Workers:**",
                "ar": "🔧 **الحد الأقصى للعمال:**"
            },
            "enabled": {
                "en": "🚀 **ENABLED**",
                "ar": "🚀 **مفعل**"
            },
            "disabled": {
                "en": "⚠️ **DISABLED**",
                "ar": "⚠️ **معطل**"
            },
            "commands": {
                "en": "**Commands:**",
                "ar": "**الأوامر:**"
            },
            "help_command": {
                "en": "• /help - Show detailed help",
                "ar": "• /help - عرض المساعدة التفصيلية"
            },
            "mystats_command": {
                "en": "• /mystats - Show your usage statistics",
                "ar": "• /mystats - عرض إحصائيات الاستخدام الخاصة بك"
            },
            "language_command": {
                "en": "• /language - Change language / تغيير اللغة",
                "ar": "• /language - تغيير اللغة / Change language"
            },
            "admin_commands": {
                "en": "**Admin Commands:**",
                "ar": "**أوامر المدير:**"
            },
            "authorize_command": {
                "en": "• /authorize &lt;user_id&gt; - Authorize a user",
                "ar": "• /authorize &lt;user_id&gt; - تخويل مستخدم"
            },
            "revoke_command": {
                "en": "• /revoke &lt;user_id&gt; - Revoke user access",
                "ar": "• /revoke &lt;user_id&gt; - إلغاء وصول المستخدم"
            },
            "users_command": {
                "en": "• /users - List authorized users",
                "ar": "• /users - قائمة المستخدمين المخولين"
            },
            "stats_command": {
                "en": "• /stats - Show system statistics",
                "ar": "• /stats - عرض إحصائيات النظام"
            },
            "admin_only": {
                "en": "This command is only available to administrators.",
                "ar": "هذا الأمر متاح فقط للمديرين."
            },
            "usage": {
                "en": "❌ **Usage:**",
                "ar": "❌ **الاستخدام:**"
            },
            "example": {
                "en": "Example:",
                "ar": "مثال:"
            },
            "user_authorized": {
                "en": "✅ **User Authorized**",
                "ar": "✅ **تم تخويل المستخدم**"
            },
            "user_granted_access": {
                "en": "User ID `{target_id}` has been granted access to the bot.",
                "ar": "تم منح معرف المستخدم `{target_id}` الوصول إلى البوت."
            },
            "invalid_user_id": {
                "en": "❌ **Invalid user ID**\n\nPlease provide a valid numeric user ID.",
                "ar": "❌ **معرف مستخدم غير صالح**\n\nيرجى تقديم معرف مستخدم رقمي صالح."
            },
            "user_access_revoked": {
                "en": "🚫 **User Access Revoked**",
                "ar": "🚫 **تم إلغاء وصول المستخدم**"
            },
            "user_no_longer_access": {
                "en": "User ID `{target_id}` no longer has access to the bot.",
                "ar": "معرف المستخدم `{target_id}` لم يعد لديه وصول إلى البوت."
            },
            "cannot_revoke_admin": {
                "en": "❌ **Cannot revoke admin access**\n\nAdmin users cannot be revoked through this command.",
                "ar": "❌ **لا يمكن إلغاء وصول المدير**\n\nلا يمكن إلغاء وصول المديرين من خلال هذا الأمر."
            },
            "system_statistics": {
                "en": "📊 **System Statistics**",
                "ar": "📊 **إحصائيات النظام**"
            },
            "total_users": {
                "en": "**Total Users:**",
                "ar": "**إجمالي المستخدمين:**"
            },
            "currently_processing": {
                "en": "**Currently Processing:**",
                "ar": "**قيد المعالجة حالياً:**"
            },
            "active_sessions": {
                "en": "**Active Sessions:**",
                "ar": "**الجلسات النشطة:**"
            },
            "total_requests": {
                "en": "**Total Requests:**",
                "ar": "**إجمالي الطلبات:**"
            },
            "total_accounts_processed": {
                "en": "**Total Accounts Processed:**",
                "ar": "**إجمالي الحسابات المعالجة:**"
            },
            "rate_limits": {
                "en": "**Rate Limits:**",
                "ar": "**حدود المعدل:**"
            },
            "max_concurrent_users": {
                "en": "• Max Concurrent Users:",
                "ar": "• الحد الأقصى للمستخدمين المتزامنين:"
            },
            "request_cooldown": {
                "en": "• Request Cooldown:",
                "ar": "• فترة انتظار الطلب:"
            },
            "requests_per_hour": {
                "en": "• Requests per Hour:",
                "ar": "• الطلبات في الساعة:"
            },
            "configuration": {
                "en": "**Configuration:**",
                "ar": "**التكوين:**"
            },
            "public_access": {
                "en": "• Public Access:",
                "ar": "• الوصول العام:"
            },
            "admin_approval_required": {
                "en": "• Admin Approval Required:",
                "ar": "• موافقة المدير مطلوبة:"
            },
            "your_statistics": {
                "en": "📈 **Your Statistics**",
                "ar": "📈 **إحصائياتك**"
            },
            "ready": {
                "en": "✅ Ready",
                "ar": "✅ جاهز"
            },
            "wait": {
                "en": "⏳ Wait {time}s",
                "ar": "⏳ انتظر {time}ث"
            },
            "last_request": {
                "en": "**Last Request:**",
                "ar": "**آخر طلب:**"
            },
            "never": {
                "en": "Never",
                "ar": "أبداً"
            },
            "yes": {
                "en": "✅ Yes",
                "ar": "✅ نعم"
            },
            "no": {
                "en": "❌ No",
                "ar": "❌ لا"
            },
            "requests_in_last_hour": {
                "en": "• Requests in last hour:",
                "ar": "• الطلبات في الساعة الماضية:"
            },
            "max_requests_per_hour": {
                "en": "• Max requests per hour:",
                "ar": "• الحد الأقصى للطلبات في الساعة:"
            },
            "cooldown_between_requests": {
                "en": "• Cooldown between requests:",
                "ar": "• فترة الانتظار بين الطلبات:"
            },
            "help_title": {
                "en": "📖 **Help - Alfa Account Data Extraction Bot**",
                "ar": "📖 **المساعدة - بوت استخراج بيانات حسابات ألفا**"
            },
            "access_required": {
                "en": "🔒 **Access Required**",
                "ar": "🔒 **الوصول مطلوب**"
            },
            "authorization_needed": {
                "en": "This bot requires authorization to use.",
                "ar": "هذا البوت يتطلب تصريحاً للاستخدام."
            },
            "contact_admin": {
                "en": "Please contact an administrator to request access.",
                "ar": "يرجى الاتصال بالمدير لطلب الوصول."
            },
            "available_commands": {
                "en": "**Available Commands:**",
                "ar": "**الأوامر المتاحة:**"
            },
            "start_description": {
                "en": "Check authorization status",
                "ar": "فحص حالة التصريح"
            },
            "help_description": {
                "en": "Show this help message",
                "ar": "عرض رسالة المساعدة هذه"
            },
            "your_user_id": {
                "en": "Your User ID:",
                "ar": "معرف المستخدم الخاص بك:"
            },
            "provide_id_to_admin": {
                "en": "Provide this ID to the administrator for authorization.",
                "ar": "قدم هذا المعرف للمدير للحصول على التصريح."
            },
            "batch_processing_enabled": {
                "en": "**⚡ Batch Processing (ENABLED):**",
                "ar": "**⚡ المعالجة المجمعة (مفعلة):**"
            },
            "processes_accounts_simultaneously": {
                "en": "Processes {count} accounts simultaneously",
                "ar": "يعالج {count} حسابات في نفس الوقت"
            },
            "uses_concurrent_workers": {
                "en": "Uses up to {count} concurrent workers",
                "ar": "يستخدم حتى {count} عمال متزامنين"
            },
            "delay_between_batches": {
                "en": "{delay}s delay between batches",
                "ar": "{delay}ث تأخير بين المجموعات"
            },
            "faster_for_multiple": {
                "en": "Significantly faster for multiple accounts",
                "ar": "أسرع بكثير للحسابات المتعددة"
            },
            "batch_processing_disabled": {
                "en": "**⚠️ Batch Processing:** DISABLED (Sequential processing)",
                "ar": "**⚠️ المعالجة المجمعة:** معطلة (معالجة تسلسلية)"
            },
            "admin_status": {
                "en": "👑 **ADMIN**",
                "ar": "👑 **مدير**"
            },
            "authorized_status": {
                "en": "✅ **AUTHORIZED**",
                "ar": "✅ **مصرح**"
            },
            "format_message": {
                "en": "**Format your message like this:**",
                "ar": "**اكتب رسالتك بهذا الشكل:**"
            },
            "what_i_extract": {
                "en": "**What I extract:**",
                "ar": "**ما أستخرجه:**"
            },
            "account_status_activation": {
                "en": "Account status and activation date",
                "ar": "حالة الحساب وتاريخ التفعيل"
            },
            "balance_validity": {
                "en": "Current balance and validity",
                "ar": "الرصيد الحالي والصلاحية"
            },
            "recharge_info": {
                "en": "Last recharge information",
                "ar": "معلومات آخر شحن"
            },
            "service_consumption": {
                "en": "Service details and consumption",
                "ar": "تفاصيل الخدمة والاستهلاك"
            },
            "secondary_numbers": {
                "en": "Secondary numbers",
                "ar": "الأرقام الثانوية"
            },
            "limits": {
                "en": "**Limits:**",
                "ar": "**الحدود:**"
            },
            "max_accounts_per_request": {
                "en": "Maximum {max} accounts per request",
                "ar": "حد أقصى {max} حسابات لكل طلب"
            },
            "processing_time_depends": {
                "en": "Processing time depends on batch settings",
                "ar": "وقت المعالجة يعتمد على إعدادات المجموعة"
            },
            "user_commands": {
                "en": "**User Commands:**",
                "ar": "**أوامر المستخدم:**"
            },
            "start_bot": {
                "en": "Start the bot",
                "ar": "تشغيل البوت"
            },
            "show_help": {
                "en": "Show this help message",
                "ar": "عرض رسالة المساعدة"
            },
            "show_stats": {
                "en": "Show your usage statistics",
                "ar": "عرض إحصائيات الاستخدام"
            },
            "change_language": {
                "en": "Change language",
                "ar": "تغيير اللغة"
            },
            "max_requests_per_hour_limit": {
                "en": "Max {max} requests per hour",
                "ar": "حد أقصى {max} طلبات في الساعة"
            },
            "cooldown_seconds": {
                "en": "{seconds}s cooldown between requests",
                "ar": "{seconds}ث انتظار بين الطلبات"
            },
            "max_concurrent_users_limit": {
                "en": "Max {max} concurrent users",
                "ar": "حد أقصى {max} مستخدمين متزامنين"
            },
            "admin_commands": {
                "en": "**👑 Admin Commands:**",
                "ar": "**👑 أوامر المدير:**"
            },
            "grant_access": {
                "en": "Grant user access",
                "ar": "منح وصول المستخدم"
            },
            "revoke_access": {
                "en": "Revoke user access",
                "ar": "إلغاء وصول المستخدم"
            },
            "list_users": {
                "en": "List all users",
                "ar": "عرض جميع المستخدمين"
            },
            "show_system_stats": {
                "en": "Show system statistics",
                "ar": "عرض إحصائيات النظام"
            },
            "privacy": {
                "en": "**Privacy:**",
                "ar": "**الخصوصية:**"
            },
            "data_processed_securely": {
                "en": "Your data is processed securely",
                "ar": "بياناتك تتم معالجتها بأمان"
            },
            "no_permanent_storage": {
                "en": "No data is stored permanently",
                "ar": "لا يتم تخزين البيانات بشكل دائم"
            },
            "results_sent_to_you": {
                "en": "Results are sent only to you",
                "ar": "النتائج ترسل إليك فقط"
            },
            "batch_settings_modifiable": {
                "en": "Batch processing settings can be modified in bot_config.py",
                "ar": "يمكن تعديل إعدادات المعالجة المجمعة في bot_config.py"
            },
            "adjust_batch_settings": {
            Language.ENGLISH: "Adjust BATCH_SIZE, MAX_CONCURRENT_WORKERS for speed control",
            Language.ARABIC: "اضبط BATCH_SIZE، MAX_CONCURRENT_WORKERS للتحكم في السرعة"
        },
        "rate_limited": {
            Language.ENGLISH: "⏳ **Rate Limited**\n\nPlease wait {wait_time} seconds before making another request.",
            Language.ARABIC: "⏳ **محدود المعدل**\n\nيرجى الانتظار {wait_time} ثانية قبل تقديم طلب آخر."
        },
        "concurrent_limit_reached": {
            Language.ENGLISH: "🚫 **Concurrent Limit Reached**\n\nMaximum {max_users} users can process accounts simultaneously.\nPlease wait for other users to finish and try again.",
            Language.ARABIC: "🚫 **تم الوصول للحد الأقصى للمستخدمين المتزامنين**\n\nيمكن لحد أقصى {max_users} مستخدمين معالجة الحسابات في نفس الوقت.\nيرجى انتظار انتهاء المستخدمين الآخرين والمحاولة مرة أخرى."
        },
            "language_selection": {
                "en": "🌐 **Language Selection**\n\nChoose your preferred language:",
                "ar": "🌐 **اختيار اللغة**\n\nاختر لغتك المفضلة:"
            },
            "language_changed": {
                "en": "✅ **Language Changed**\n\nYour language has been set to English.",
                "ar": "✅ **تم تغيير اللغة**\n\nتم تعيين لغتك إلى العربية."
            },

            "wait_before_request": {
                "en": "Please wait {time:.1f} seconds before making another request.",
                "ar": "يرجى الانتظار {time:.1f} ثانية قبل تقديم طلب آخر."
            },
            "concurrent_limit_reached": {
                "en": "🚫 **Concurrent Limit Reached**",
                "ar": "🚫 **تم الوصول للحد الأقصى المتزامن**"
            },
            "max_users_processing": {
                "en": "Maximum {max_users} users can process accounts simultaneously.\nPlease wait for other users to finish and try again.",
                "ar": "يمكن لحد أقصى {max_users} مستخدم معالجة الحسابات في نفس الوقت.\nيرجى انتظار انتهاء المستخدمين الآخرين والمحاولة مرة أخرى."
            },
            "processing_started": {
                "en": "🚀 **Processing Started**",
                "ar": "🚀 **بدأت المعالجة**"
            },
            "processing_accounts": {
                "en": "Processing {count} accounts...",
                "ar": "معالجة {count} حساب..."
            },
            "batch_mode": {
                "en": "**Mode:** Batch Processing ({batch_size} accounts per batch)",
                "ar": "**الوضع:** المعالجة المجمعة ({batch_size} حساب لكل مجموعة)"
            },
            "sequential_mode": {
                "en": "**Mode:** Sequential Processing",
                "ar": "**الوضع:** المعالجة المتسلسلة"
            },
            "estimated_time": {
                "en": "**Estimated Time:** {time} minutes",
                "ar": "**الوقت المقدر:** {time} دقيقة"
            },
            "please_wait": {
                "en": "Please wait while I process your accounts...",
                "ar": "يرجى الانتظار بينما أقوم بمعالجة حساباتك..."
            },
            "processing_complete": {
                "en": "✅ **Processing Complete**",
                "ar": "✅ **اكتملت المعالجة**"
            },
            "results_summary": {
                "en": "**Results Summary:**",
                "ar": "**ملخص النتائج:**"
            },
            "successful": {
                "en": "• Successful:",
                "ar": "• نجح:"
            },
            "failed": {
                "en": "• Failed:",
                "ar": "• فشل:"
            },
            "total_processed": {
                "en": "• Total Processed:",
                "ar": "• إجمالي المعالج:"
            },
            "processing_time": {
                "en": "• Processing Time:",
                "ar": "• وقت المعالجة:"
            },
            "csv_file_attached": {
                "en": "📎 CSV file with all results is attached above.",
                "ar": "📎 ملف CSV مع جميع النتائج مرفق أعلاه."
            },
            "error_occurred": {
                "en": "❌ **Error Occurred**",
                "ar": "❌ **حدث خطأ**"
            },
            "invalid_format": {
                "en": "Invalid message format. Please provide account numbers and password.",
                "ar": "تنسيق الرسالة غير صالح. يرجى تقديم أرقام الحسابات وكلمة المرور."
            },
            "too_many_accounts": {
                "en": "Too many accounts. Maximum allowed: {max_accounts}",
                "ar": "عدد كبير جداً من الحسابات. الحد الأقصى المسموح: {max_accounts}"
            },
            "invalid_account_number": {
                "en": "Invalid account number: {account}. Account numbers should contain only digits.",
                "ar": "رقم حساب غير صالح: {account}. يجب أن تحتوي أرقام الحسابات على أرقام فقط."
            },
            "provide_at_least_one": {
                "en": "Please provide at least one account number and a password.",
                "ar": "يرجى تقديم رقم حساب واحد على الأقل وكلمة مرور."
            },
            "access_denied_message": {
                "en": "🔒 **Access Denied**\n\nYou are not authorized to use this bot.",
                "ar": "🔒 **تم رفض الوصول**\n\nأنت غير مخول لاستخدام هذا البوت."
            },
            "select_language": {
                "en": "🌐 **Language Selection**\n\nChoose your preferred language:",
                "ar": "🌐 **اختيار اللغة**\n\nاختر لغتك المفضلة:"
            },
            "access_denied_short": {
                "en": "Access denied",
                "ar": "تم رفض الوصول"
            },
            "invalid_language": {
                "en": "Invalid language selection",
                "ar": "اختيار لغة غير صالح"
            },
            "system_statistics": {
                "en": "📊 **System Statistics**",
                "ar": "📊 **إحصائيات النظام**"
            },
            "total_users": {
                "en": "**Total Users:**",
                "ar": "**إجمالي المستخدمين:**"
            },
            "currently_processing": {
                "en": "**Currently Processing:**",
                "ar": "**قيد المعالجة حالياً:**"
            },
            "active_sessions": {
                "en": "**Active Sessions:**",
                "ar": "**الجلسات النشطة:**"
            },
            "total_requests": {
                "en": "**Total Requests:**",
                "ar": "**إجمالي الطلبات:**"
            },
            "total_accounts_processed": {
                "en": "**Total Accounts Processed:**",
                "ar": "**إجمالي الحسابات المعالجة:**"
            },
            "rate_limits": {
                "en": "**Rate Limits:**",
                "ar": "**حدود المعدل:**"
            },
            "max_concurrent_users": {
                "en": "• Max Concurrent Users:",
                "ar": "• الحد الأقصى للمستخدمين المتزامنين:"
            },
            "request_cooldown": {
                "en": "• Request Cooldown:",
                "ar": "• فترة انتظار الطلب:"
            },
            "requests_per_hour": {
                "en": "• Requests per Hour:",
                "ar": "• الطلبات في الساعة:"
            },
            "configuration": {
                "en": "**Configuration:**",
                "ar": "**التكوين:**"
            },
            "public_access": {
                "en": "• Public Access:",
                "ar": "• الوصول العام:"
            },
            "admin_approval_required": {
                "en": "• Admin Approval Required:",
                "ar": "• موافقة المدير مطلوبة:"
            },
            "your_statistics": {
                "en": "📈 **Your Statistics**",
                "ar": "📈 **إحصائياتك**"
            },
            "ready": {
                "en": "✅ Ready",
                "ar": "✅ جاهز"
            },
            "wait": {
                "en": "⏳ Wait {time}s",
                "ar": "⏳ انتظر {time}ث"
            },
            "last_request": {
                "en": "**Last Request:**",
                "ar": "**آخر طلب:**"
            },
            "never": {
                "en": "Never",
                "ar": "أبداً"
            },
            "yes": {
                "en": "✅ Yes",
                "ar": "✅ نعم"
            },
            "no": {
                "en": "❌ No",
                "ar": "❌ لا"
            },
            "requests_in_last_hour": {
                "en": "• Requests in last hour:",
                "ar": "• الطلبات في الساعة الماضية:"
            },
            "max_requests_per_hour": {
                "en": "• Max requests per hour:",
                "ar": "• الحد الأقصى للطلبات في الساعة:"
            },
            "cooldown_between_requests": {
                "en": "• Cooldown between requests:",
                "ar": "• فترة الانتظار بين الطلبات:"
            }
        }
    
    def set_user_language(self, user_id: int, language: Language) -> None:
        """Set user's preferred language."""
        self.user_preferences[user_id] = language
    
    def get_user_language(self, user_id: int) -> Language:
        """Get user's preferred language, default to English."""
        return self.user_preferences.get(user_id, Language.ENGLISH)
    
    def get_text(self, key: str, user_id: int, **kwargs) -> str:
        """Get translated text for user's language."""
        language = self.get_user_language(user_id)
        
        if key not in self.translations:
            return f"[Missing translation: {key}]"
        
        text = self.translations[key].get(language.value, self.translations[key].get("en", f"[Missing: {key}]"))
        
        # Format with provided kwargs
        if kwargs:
            try:
                text = text.format(**kwargs)
            except (KeyError, ValueError) as e:
                return f"[Format error in {key}: {e}]"
        
        return text
    
    def get_language_keyboard(self) -> list:
        """Get inline keyboard for language selection."""
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        
        keyboard = [
            [InlineKeyboardButton("🇺🇸 English", callback_data="lang_en")],
            [InlineKeyboardButton("🇸🇦 العربية", callback_data="lang_ar")]
        ]
        return InlineKeyboardMarkup(keyboard)

# Global language manager instance
language_manager = LanguageManager()