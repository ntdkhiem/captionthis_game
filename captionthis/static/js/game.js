const serverURL = location.protocol + "//" + document.domain + ":" + location.port + "/game";
let serverPayload = {
    reconnection: false,
    transports: ['websocket'],
    // path: '/',
}

let self = ''
let roomID = ''
let played_rounds = 0
let total_rounds = 0
let memer = ''
let players = {}
let currSect = 'join'
let templateKey = ''

let timer
let counter
let socket

startListen = (socket) => {

    socket.on('connect', () => {
        console.log('Server connected')
    })

    socket.on('disconnect', () => {
        console.log('server disconnected!')
    })

    socket.on('gameConnected', (data) => {
        console.log('Received gameConnected msg', data)
        self = data[0]
        document.querySelector('#roomID').innerText = roomID;
        updatePlayersList(data[1])
        total_rounds = data[2]
        updateRoundInfo()
        switchPage('wait')
    })

    // Await for addToPlayerBoard implementation
    socket.on('gameDisconnected', function (data) {
        console.log('Received gameDisconnected msg', data)
        // Redirect client back to home page.
        modal = new bootstrap.Modal(document.getElementById('closedGameModal'), {
            backdrop: 'static',
        }).show()
        resetGame()
        stopTimer()
        document.querySelector('#playerBoard').innerHTML = ''

        // reset important global variables
        self = ''
        roomID = ''
        played_rounds = 0
        total_rounds = 0
        memer = ''
        players = {}
        templateKey = ''
    })

    socket.on('gamePlayerConnected', (data) => {
        console.log('Received gamePlayerConnected msg', data)
        if (Object.keys(data)[0] != self) {
            updatePlayersList(data);
        }
        // TODO: Send a notification msg
    })

    socket.on('gamePlayerDisconnected', (data) => {
        console.log('Player ' + data + ' disconnected')
        removePlayerFromBoard(data)
        delete players[data]
    })

    socket.on('gameFull', () => {
        console.log('Received gameFull msg')
        document.querySelector('#wait').querySelector('.waitMsg').innerText = 'The room is full.'
    })

    socket.on('gameOpen', () => {
        console.log('Received gameOpen msg')
        document.querySelector('#wait').querySelector('h4').innerText = 'Waiting for more people'
    })

    socket.on('gameStart', (data) => {
        console.log('Received gameStart msg', data)
        resetGame()
        templateKey = data.template.key
        memer = data.memer
        if (memer == self) {
            constructTemplate(data.template)
        }
        else {
            console.log('waiting for memer')
            document.querySelector('section#caption')
                .querySelector('.nonOverlay')
                .classList.remove('hidden')
        }
        toggleMemerIcon()
        played_rounds = data.total_rounds - data.rounds_remain
        updateRoundInfo()
        switchPage('caption')
    })

    socket.on('gameReset', () => {
        console.log('Received gameReset msg')
        resetGame()
    })

    socket.on('gameException', (data) => {
        console.log('Received gameException', data)
        addAlert(data, 'danger')
    })

    socket.on('gameEnd', (data) => {
        console.log('Received gameEnd msg', data)
        constructLeaderboard(data)
        // switch to leaderboard after 5 seconds
        setTimeout(() => {
            resetPlayerState()
            switchPage('leaderboard')
        }, 5000)
    })

    socket.on('gameSwitchPage', (data) => {
        console.log('Received gameSwitchPage msg', data)
        switchPage(data)
    })

    socket.on('gamePlayerReady', (data) => {
        console.log('Received gamePlayerReady msg')
        playerReady(data)
    })

    socket.on('gameTimeStart', (data) => {
        console.log('Received gameTimeStart msg', data)
        counter = data
        startTimer()
    })

    socket.on('gameTimeUp', () => {
        console.log('Received gameTimeUp msg')
        stopTimer()
    })

    socket.on('gameReady', () => {
        console.log('Received gameReady msg')
        document.querySelector('#btnPlay').disabled = false
    })

    socket.on('gameGetCaption', (data) => {
        console.log('Received gameGetCaption msg', data)
        if (memer !== self) {
            constructVoteSection(data.key)
        } else {
            document.querySelector('section#vote')
                .querySelector('.nonOverlay')
                .classList.remove('hidden')
        }
    })

    socket.on('gameGetScore', (score) => {
        console.log('Received gameGetScore msg', score)
        if (memer !== self) {
            document.querySelector('section#vote > div.memeContainer > span#finalScore')
                .innerText = score
        }
    })

    socket.on('gameGetWinner', (data) => {
        console.log('Received gameGetWinner msg', data)
        victSect = document.querySelector('#victory')
        if (data.length) {
            data.forEach(item => {
                div = document.createElement('div')
                div.id = `winner_${item[0]}`
                div.className = 'col-4'
                img = createImg(item[1])
                img.className = 'img-fluid'
                score = document.createElement('div')
                score.className = 'score'
                score.innerText = `${item[2]} points`
                nameDiv = document.createElement('div')
                nameDiv.className = 'name'
                nameDiv.innerText = players[item[0]].name
                div.appendChild(img)
                div.appendChild(score)
                div.appendChild(nameDiv)
                victSect.querySelector('.row').appendChild(div)
            })
        }
        switchPage('victory')
    })
}

// JOIN
joinEl = document.querySelector('#join')
for (form of joinEl.querySelectorAll('form')) {
    form.addEventListener('submit', e => {
        e.preventDefault()
        console.log('Fetching from the server')
        data = new FormData(e.target)
        fetch(e.target.action, {
            method: 'POST',
            body: data,
        })
            .then(res => res.json())
            .then(res => {
                if (res.errors) {
                    Object.entries(res.errors).forEach(field => {
                        el = document.getElementById(field[0])
                        errors = el.parentNode.querySelector('#errors')
                        // clear the field first
                        errors.innerHTML = ''
                        // add new errors
                        for (error of field[1]) {
                            var node = document.createElement('li')
                            node.innerText = error
                            node.classList.add('text-danger')
                            errors.appendChild(node)
                        }
                    })
                }
                else if (res.data.id) {
                    roomID = res.data.id
                    total_rounds = data.get('total_games')
                    switchPage('login')
                }
                else {
                    addAlert(res.data, 'warning')
                }
            })
            .catch(err => {console.log(err)})
    })
}

document.querySelector('#joinRandom').addEventListener('click', () => {
    csrf_token = document.querySelector('meta[name="_token"]').getAttribute('content')
    fetch('/joinRandom', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
            'X-CSRFToken': csrf_token,
        },
    })
        .then(res => res.json())
        .then(res => {
            if (res.data.id) {
                roomID = res.data.id
                switchPage('login')
            } else {
                addAlert(res.data, 'warning')
            }
        })
        .catch(err => {
            console.log(err)
        })
})

// LOGIN
document.querySelector('#createName').addEventListener('submit', e => {
    e.preventDefault()
    console.log(e)
    serverPayload.query = {
        id: roomID,
        name: e.target[0].value,
    }
    socket = io.connect(serverURL, serverPayload)
    startListen(socket)
})

// WAIT
document.querySelector('#btnPlay').addEventListener('click', (e) => imReady(e))
document.querySelector('#btnNextRound').addEventListener('click', (e) => imReady(e))

imReady = (e) => {
    socket.emit('playerReady')
    document.querySelector(`button#${e.target.id}`).disabled = true
}

// CAPTION
document.querySelector('#captionForm').addEventListener('submit', e => {
    e.preventDefault()
    console.log(e.target)
    inputs = document.querySelectorAll('#captionForm > input[type="text"]')
    lines = []
    inputs.forEach(input => {
        lines.push(input.value)
    })
    socket.emit('captionSubmit', {'key': templateKey, 'lines': lines})

    // reset and disable inputs in the form
    e.target.reset()
    for (el of e.target.elements) {
        el.disabled = true
    }
})

document.querySelector('#previewBtn').addEventListener('click', () => updatePreview())
updatePreview = () => {
    capSect = document.querySelector('#caption')
    img = capSect.querySelector('img')
    if (img) {
        key = img.getAttribute('id')
        lines = capSect.querySelectorAll('input[type="text"]')
        encoded_lines = '&'
        lines.forEach(line => {
            encoded_line = encodeURIComponent(line.value || ' ')
            encoded_lines += `lines[]=${encoded_line}&`
        })
        url = `/images/preview?template=${key}&${encoded_lines}`
        img.src = url
    }
}

// VOTE
constructVoteSection = (key) => {
    // Add image to vote section
    console.log(roomID, templateKey, key)
    img = createImg(key)
    img.className = 'meme'
    document.querySelector('section#vote > div.memeContainer').appendChild(img)
}

document.querySelector('section#vote').querySelectorAll('button.option').forEach(e => {
    e.addEventListener('click', (e) => selectOption(e.target))
})

selectOption = (e) => {
    console.log(e)
    parent = e.parentNode
    parent.querySelectorAll('.option').forEach(c => {
        if (!c.isEqualNode(e)) {
            if (c.classList.contains('active')) {
                c.classList.remove('active')
            }
        }
    })
    e.classList.add('active')
}

document.querySelector('#btnVote').addEventListener('click', () => vote())
vote = () => {
    e = document.querySelector('section#vote > div.options > button.active')
    if (e) {
        socket.emit('voteSubmit', e.textContent)
        document.querySelector('#btnVote').disabled = true
        document.querySelector('section#vote > .options')
            .childNodes.forEach(n => {n.disabled = true})
    }
}

// Utilities
document.querySelector('#btnReturn').addEventListener('click', () => switchPage('join'))

updateRoundInfo = () => {
    roundsMsg = `Round ${played_rounds} of ${total_rounds}`
    document.querySelector('#rounds').innerText = roundsMsg
}

updatePlayersList = (plrs) => {
    Object.keys(plrs).forEach((k) => {
        players[k] = plrs[k]
        addToPlayerBoard(k, plrs[k].name)
    })
}

addToPlayerBoard = (id, name) => {
    div = document.createElement('div')
    div.className = 'd-flex align-items-center my-3 mx-2'
    div.id = `_${id}`
    img = document.createElement('img')
    img.src = '/static/img/player.jpg'
    img.className = 'avatar me-2'
    pName = document.createElement('p')
    pName.innerText = name
    pName.className = 'fs-5'
    spanReady = document.createElement('span')
    spanReady.className = 'ready-icon hidden ms-auto'
    spanEye = document.createElement('span')
    spanEye.className = 'eye-icon hidden ms-auto'
    div.appendChild(img)
    div.appendChild(pName)
    div.appendChild(spanEye)
    div.appendChild(spanReady)
    document.querySelector('#playerBoard').appendChild(div)
}

resetPlayerState = () => {
    playerBoard = document.querySelector('#playerBoard').children
    for (playerEl of playerBoard) {
        playerEl.querySelector('.ready-icon').classList.add('hidden')
        playerEl.querySelector('.eye-icon').classList.add('hidden')
    }
}

constructTemplate = (template) => {
    captionSect = document.querySelector('#caption')
    form = captionSect.querySelector('#captionForm')
    for (i = 0; i < template.lines; i++) {
        input = document.createElement('input')
        input.setAttribute("type", "text");
        input.setAttribute("placeholder", "enter text here...")
        input.className = 'form-control form-control-lg mb-3'
        input.id = `caption${i}`
        input.required = true
        form.prepend(input)
    }
    img = document.createElement('img')
    img.src = template.example
    img.id = template.key
    img.className = 'img-fluid mb-3'
    captionSect.querySelector('#previewContainer').prepend(img)
}

constructLeaderboard = (data) => {
    groupedPlayers = groupByPoints(Object.entries(data))
    keys = Object.keys(groupedPlayers).reverse()    // originally sorted from lowest to highest
    leaderboardSect = document.querySelector('section#leaderboard')
    referenceNode = leaderboardSect.querySelector('button#btnNextRound')
    for (var i = 0; i < keys.length; i++) {
        place = i == 0 ? 'first' : i == 1 ? 'second' : 'third'
        groupedPlayers[keys[i]].forEach(plr => {
            div = document.createElement('div')
            div.className = `${place}-place`
            p = document.createElement('p')
            p.innerText = plr[1].name
            if (place == 'first') {
                icon = document.createElement('i')
                icon.className = 'fas fa-crown'
                p.appendChild(icon)
            }
            divScore = document.createElement('div')
            divScore.innerText = `${keys[i]} points`
            div.appendChild(p)
            div.appendChild(divScore)
            leaderboardSect.insertBefore(div, referenceNode)
        })
    }
}

resetGame = () => {
    // Re-enable forms and reset display data

    let captionSect = document.querySelector('#caption')
    let voteSect = document.querySelector('#vote')
    let victorySect = document.querySelector('#victory')
    let leaderboardSect = document.querySelector('#leaderboard')

    // caption section
    img = captionSect.querySelector('#previewContainer > img')
    if (img) {
        img.parentNode.removeChild(img)
    }

    let form = captionSect.querySelector('#captionForm')
    inputText = form.querySelectorAll('input[type="text"]')
    inputText.forEach(input => {form.removeChild(input)})
    form.querySelector('input[type="submit"]').disabled = false

    overlay = captionSect.querySelector('.nonOverlay')
    if (!overlay.classList.contains('hidden')) {
        overlay.classList.add('hidden')
    }

    // vote section
    overlay = voteSect.querySelector('.nonOverlay')
    if (!overlay.classList.contains('hidden')) {
        overlay.classList.add('hidden')
    }

    memeContainer = voteSect.querySelector('div.memeContainer')
    img = memeContainer.querySelector('img')
    if (img) {
        memeContainer.removeChild(img)
    }

    memeContainer.querySelector('span#finalScore').innerText = ''
    voteSect.querySelectorAll('.option').forEach(c => {
        if (c.classList.contains('active')) {
            c.classList.remove('active')
        }
    })
    voteSect.querySelector('#btnVote').disabled = false
    voteSect.querySelector('.options').childNodes.forEach(n => {n.disabled = false})

    // victory section
    victorySect.querySelector('.row').innerHTML = ''

    // leaderboard section
    // selector all divs containing 'place' in class attribute
    leaderboardSect.querySelectorAll('div[class*="place"]')
        .forEach(div => leaderboardSect.removeChild(div))
    leaderboardSect.querySelector('#btnNextRound').disabled = false

    resetPlayerState()
}

switchPage = (npage) => {
    document.getElementById(currSect).classList.remove('visible')
    document.getElementById(npage).classList.add('visible')
    currSect = npage
}

playerReady = (pid) => {
    document.querySelector(`#_${pid}`)
        .querySelector('.ready-icon')
        .classList.remove('hidden')
}

toggleMemerIcon = () => {
    document.querySelector(`#_${memer}`)
        .querySelector('.eye-icon')
        .classList.remove('hidden')
}

startTimer = () => {
    timer = setInterval(() => {
        document.querySelector('#timer').innerText = counter
        if (counter === 0) {
            clearInterval(timer)
        }
        else {
            counter--
        }
    }, 1000)
}

stopTimer = () => {
    clearInterval(timer)
    counter = 0
    document.querySelector('#timer').innerText = counter
}

addAlert = (text, lvl) => {
    div = document.createElement('DIV')
    div.className = `alert alert-${lvl} alert-dismissible fade show fixed-top`
    div.setAttribute('role', 'alert')
    div.innerText = text
    btnClose = document.createElement('button')
    btnClose.setAttribute('type', 'button')
    btnClose.setAttribute('class', 'btn-close ms-auto')
    btnClose.setAttribute('data-bs-dismiss', 'alert')
    btnClose.setAttribute('aria-label', 'Close')
    btnClose.className = 'btn-close'
    div.appendChild(btnClose)
    document.querySelector('body').prepend(div)
}

removePlayerFromBoard = (pid) => {
    playersEl = document.querySelector('#playerBoard')
    children = playersEl.querySelectorAll('div')
    children.forEach(child => {
        if (child.id == `_${pid}`) {
            playersEl.removeChild(child)
            return
        }
    })
}

createImg = (key) => {
    img = document.createElement('img')
    img.src = `/image/${roomID}/${templateKey}/${key}.jpg`
    return img
}

// inspired by https://stackoverflow.com/questions/14696326/break-array-of-objects-into-separate-arrays-based-on-a-property
groupByPoints = (arr) => {
    return arr.reduce((memo, item) => {
        if (!memo[item[1]['points']]) {memo[item[1]['points']] = []}
        memo[item[1]['points']].push(item)
        return memo
    }, {})
}
