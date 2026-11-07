package com.konecto.series76.splash

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.konecto.series76.data.AssistantRepository
import com.konecto.series76.data.AuthRepository
import kotlinx.coroutines.async
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withTimeoutOrNull

/**
 * Pings /health while the splash is visible. [done] flips after max([minMs], health time),
 * capped at [maxMs]. The ping result never changes navigation: screens show offline themselves.
 * [signedIn] says whether a stored session exists (decides Login vs Conversations); read before [done] flips.
 */
class SplashViewModel(
    private val repo: AssistantRepository,
    private val auth: AuthRepository,
    private val minMs: Long = 600,
    private val maxMs: Long = 1500,
) : ViewModel() {

    private val _done = MutableStateFlow(false)
    val done: StateFlow<Boolean> = _done

    private val _signedIn = MutableStateFlow(false)
    val signedIn: StateFlow<Boolean> = _signedIn

    init {
        viewModelScope.launch {
            val restored = async { auth.restore() } // local read, in parallel with the wait below
            // Health runs in parallel with the minimum wait; the timeout caps the total.
            withTimeoutOrNull(maxMs) {
                val ping = launch { repo.health() } // result ignored: screens show offline themselves
                delay(minMs)
                ping.join()
            }
            _signedIn.value = restored.await() != null
            _done.value = true
        }
    }

    companion object {
        fun factory(repo: AssistantRepository, auth: AuthRepository): ViewModelProvider.Factory =
            viewModelFactory { initializer { SplashViewModel(repo, auth) } }
    }
}
