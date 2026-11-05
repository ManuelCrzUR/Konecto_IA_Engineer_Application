# Libraries (Retrofit, OkHttp, kotlinx.serialization, coroutines) ship consumer rules.
# Only app-specific needs are listed here; no blanket keep of the whole app.

# Attributes needed by Retrofit (generic return types of suspend funs) and serialization.
-keepattributes Signature, InnerClasses, EnclosingMethod, RuntimeVisibleAnnotations, AnnotationDefault

# API models in com.konecto.series76.data: keep @Serializable classes' companion serializers.
-keepclassmembers @kotlinx.serialization.Serializable class com.konecto.series76.data.** {
    *** Companion;
    kotlinx.serialization.KSerializer serializer(...);
}

# Retrofit service interface(s): methods are invoked through a reflective proxy.
-keep interface com.konecto.series76.data.ApiService
-keepclassmembers,allowobfuscation interface com.konecto.series76.data.ApiService {
    @retrofit2.http.* <methods>;
}
