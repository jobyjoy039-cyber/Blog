# kotlinx.serialization: keep generated serializers for DTOs
-keepattributes *Annotation*, InnerClasses
-keep,includedescriptorclasses class com.ugcstudio.app.data.remote.**$$serializer { *; }
-keepclassmembers class com.ugcstudio.app.data.remote.** { *** Companion; }
-keepclasseswithmembers class com.ugcstudio.app.data.remote.** { kotlinx.serialization.KSerializer serializer(...); }
# Retrofit interfaces
-keep,allowobfuscation,allowshrinking interface retrofit2.Call
-keep,allowobfuscation,allowshrinking class kotlin.coroutines.Continuation
