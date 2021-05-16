chrome.contextMenus.create({
    id: "fake-news-reporter",
    title: "See if it is fake!",
    contexts: ["page"],
});

chrome.contextMenus.create({
    id: "fake-news-reporter-over-link",
    title: "See if it is fake!",
    contexts: ["link"],
});

var notification_id = "";
var response_data = null;
var main_url = null;
var returned = null;

chrome.contextMenus.onClicked.addListener((info, tab) => {
    if (info.menuItemId === "fake-news-reporter") {
		sendRequest(tab.url, true);
    }
});

chrome.notifications.onButtonClicked.addListener(function(notifId, btnIdx) {
    if (notifId === notification_id) {
		if (btnIdx == 0)
			chrome.tabs.create({url: `http://127.0.0.1:8080/further_details?url=${main_url}&sources=${response_data}`});
		if (btnIdx == 1){
			chrome.notifications.clear(notifId);
			sendRequest(main_url, false);
		}
    }
});

function sendRequest(url, from_cache) {
      returned = false;
      analyzeURL(url, from_cache).then((data)=>{
		returned = true;
		let splitted_data = data.split(", ");
		let real_prob = splitted_data[0].slice(1,);
		let fake_prob = splitted_data[1].slice(0,-2);
		response_data = btoa(splitted_data.join(" "));
        chrome.notifications.create("", {
            title: 'Result: ',
            message: `\nThis likely real: ${real_prob.slice(0,4)}\nThis likely fake: ${fake_prob.slice(0,4)}`,
            type: 'basic',
			iconUrl: `icons/sign${+(real_prob > fake_prob)}.png`,
			buttons: [{
       	 		title: "See why",
    		}, {
        		title: "Rerun from scratch",
    		}]
          }, function(notificationId) { notification_id = notificationId;});
        }).catch((data)=>{
          chrome.notifications.create({
              title: `Error:`,
              message: `${data}`,
              type: 'basic',
			  iconUrl: 'icons/sign0.png'
            });
        });
}

function sleep (time) {
  return new Promise((resolve) => setTimeout(resolve, time));
}

function analyzeURL(url, from_cache){
  main_url = url;

  return new Promise(function(resolve,reject){

    let title_contents = [];
    var xhr = new XMLHttpRequest();
    xhr.onreadystatechange = () => {
    if (xhr.readyState == 4 && xhr.status == 200) {
          resolve(xhr.response);      
      }
    };

    xhr.onerror = (evt) => {
        reject(evt);
    };
    try {
		if (from_cache)
        	xhr.open('GET', "http://127.0.0.1:8080/url="+url+"&from_cache=true", true);
		else
			xhr.open('GET', "http://127.0.0.1:8080/url="+url+"&from_cache=false", true);

        xhr.send();
		sleep(1000).then(() => {
  			if (!returned) {
				chrome.notifications.create("", {
                	title: 'Query is running...',
                	message: "",
                	type: 'basic',
                	iconUrl: "icons/load.png"
            	});
			} 
		});

		
    }
    catch (ex) {
        reject(ex);
    }
  });
}
