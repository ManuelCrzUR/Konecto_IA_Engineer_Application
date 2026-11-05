package com.konecto.series76.conversations

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.focus.onFocusChanged
import com.konecto.series76.ui.AxelHeader
import com.konecto.series76.ui.axel.AxelAvatar
import com.konecto.series76.ui.axel.AxelState
import com.konecto.series76.ui.theme.AxelTheme
import com.konecto.series76.ui.theme.ThemeMode

@Composable
fun ConversationsHeader(
    themeMode: ThemeMode,
    onThemeMode: (ThemeMode) -> Unit,
    query: String,
    onQueryChange: (String) -> Unit,
) {
    AxelHeader(contentPadding = PaddingValues(start = 20.dp, end = 20.dp, top = 16.dp, bottom = 12.dp)) {
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                AxelAvatar(AxelState.IDLE, size = 32.dp)
                Column(Modifier.weight(1f)) {
                    Text("Axel", style = AxelTheme.typography.title.copy(fontSize = 22.sp))
                    Text("Your conversations", style = AxelTheme.typography.label, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                ThemeButton(themeMode, onThemeMode)
            }
            SearchField(query, onQueryChange)
        }
    }
}

@Composable
private fun ThemeButton(current: ThemeMode, onSelect: (ThemeMode) -> Unit) {
    var open by remember { mutableStateOf(false) }
    val shape = RoundedCornerShape(16.dp)
    Box {
        IconButton(
            onClick = { open = true },
            modifier = Modifier.size(48.dp).background(MaterialTheme.colorScheme.surface, shape)
                .border(1.dp, AxelTheme.colors.divider, shape).testTag("theme_button"),
        ) {
            Icon(if (AxelTheme.colors.isDark) MoonIcon else SunIcon, contentDescription = "Theme", modifier = Modifier.size(22.dp))
        }
        DropdownMenu(expanded = open, onDismissRequest = { open = false }) {
            listOf(ThemeMode.DARK, ThemeMode.LIGHT, ThemeMode.SYSTEM).forEach { mode ->
                DropdownMenuItem(
                    text = { Text(mode.name.lowercase().replaceFirstChar { it.uppercase() }) },
                    trailingIcon = {
                        if (mode == current) Icon(Icons.Default.Check, contentDescription = "Selected", tint = MaterialTheme.colorScheme.primary)
                    },
                    onClick = { open = false; onSelect(mode) },
                    modifier = Modifier.testTag("theme_option_${mode.name}"),
                )
            }
        }
    }
}

@Composable
private fun SearchField(query: String, onQueryChange: (String) -> Unit) {
    var focused by remember { mutableStateOf(false) }
    val shape = RoundedCornerShape(16.dp)
    val border = if (focused) AxelTheme.colors.accentText else AxelTheme.colors.divider
    Surface(color = MaterialTheme.colorScheme.surface, shape = shape, border = BorderStroke(1.dp, border)) {
        Box(Modifier.fillMaxWidth().height(48.dp), contentAlignment = Alignment.CenterStart) {
            Icon(
                Icons.Default.Search, contentDescription = null, tint = AxelTheme.colors.textTertiary,
                modifier = Modifier.padding(start = 14.dp).size(20.dp),
            )
            BasicTextField(
                value = query,
                onValueChange = onQueryChange,
                singleLine = true,
                textStyle = MaterialTheme.typography.bodyMedium.copy(color = MaterialTheme.colorScheme.onSurface),
                cursorBrush = SolidColor(MaterialTheme.colorScheme.primary),
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                modifier = Modifier.fillMaxWidth().padding(start = 44.dp, end = 48.dp)
                    .testTag("search_field").onFocusChanged { focused = it.isFocused },
                decorationBox = { inner ->
                    Box(contentAlignment = Alignment.CenterStart) {
                        if (query.isEmpty()) {
                            Text("Search chats, part numbers…", style = MaterialTheme.typography.bodyMedium, color = AxelTheme.colors.textTertiary)
                        }
                        inner()
                    }
                },
            )
            if (query.isNotEmpty()) {
                IconButton(onClick = { onQueryChange("") }, modifier = Modifier.align(Alignment.CenterEnd).size(44.dp).testTag("search_clear")) {
                    Icon(Icons.Default.Close, contentDescription = "Clear search", tint = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.size(18.dp))
                }
            }
        }
    }
}
