package com.konecto.series76.chat

/** Removes markdown bold markers only. Never touches digits or any other character. */
fun plainText(s: String): String = s.replace("**", "")
