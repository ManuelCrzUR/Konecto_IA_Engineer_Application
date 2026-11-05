package com.konecto.series76.splash

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.background
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.konecto.series76.App
import com.konecto.series76.ui.axel.AxelAvatar
import com.konecto.series76.ui.axel.AxelState
import com.konecto.series76.ui.theme.AxelTheme

@Composable
fun SplashScreen(
    onDone: () -> Unit,
    viewModel: SplashViewModel = defaultViewModel(),
) {
    val done by viewModel.done.collectAsStateWithLifecycle()
    val onDoneNow by rememberUpdatedState(onDone)
    LaunchedEffect(done) { if (done) onDoneNow() }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .testTag("splash"),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        AxelAvatar(state = AxelState.IDLE, size = 112.dp)
        Spacer(Modifier.height(16.dp))
        Text("Axel", style = AxelTheme.typography.title, color = MaterialTheme.colorScheme.onBackground)
        Spacer(Modifier.height(4.dp))
        Text("Series 76 actuator assistant", color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun defaultViewModel(): SplashViewModel {
    val app = LocalContext.current.applicationContext as App
    return viewModel(factory = SplashViewModel.factory(app.container.repository))
}
