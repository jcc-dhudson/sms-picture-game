var people;$("#alertBtn").click((function(){$("#menuModal").modal("show")})),$("#nav-sendToken").click((function(){$("#menuModal").modal("hide"),$("#sendModal").modal("show")})),$("#nav-submissions").click((function(){window.location.href="/submissions"})),$("#nav-groups").click((function(){window.location.href="/admin"})),$.get("/list",(function(o,e){people=o})),sendModalOriginal=$("#sendModal").html(),$("#sendMessageButton").click((function(){for(modalOriginal=$("#sendModal").html(),message=$("#sendMessageInput").val(),max_uploads=$("#sendMaxUploads").val(),console.log(max_uploads),ids=[],i=0;i<people.length;i++)ids.push(people[i].person_id);console.log(message,ids),modalOriginal=$("#sendModal-body").html('Sending "'+message+'" and a link to '+ids.length+" participants."),$.ajax("/sendtoken",{data:JSON.stringify({message:message,ids:ids,max_uploads:max_uploads}),contentType:"application/json",type:"POST"}).done((function(o){modalOriginal=$("#sendModal-body").html("Sent tokens. Server responded: <br />"+o)})),$("#sendModal-footer").html('<button type="button" class="btn btn-secondary btn-block" id="sendAckBtn" >Acknowledge</button>'),$("#sendAckBtn").click((function(){$("#sendModal").modal("hide"),$("#sendModal").html(sendModalOriginal)}))})),$("#nav-leaderboard").click((function(){$("#menuModal").modal("hide"),$("#leaderboard-table-body").html(""),$.get("/getscores",(function(o){for(o.sort((function(o,e){return e.score-o.score})),i=0;i<o.length;i++)$("#leaderboard-table-body").append('<tr><th scope="row">'+o[i].name+'</th><td><b><div style="font-size: large;" class="badge bg-light text-dark">'+o[i].score+"</div></b></td></tr>");console.log(o)})),$("#leaderboard").modal("show")})),$("#nav-createGroup").click((function(){$("#menuModal").modal("hide"),$("#createGroupBtn").click((function(){$.ajax("/groups",{data:JSON.stringify({name:$("#groupName").val()}),contentType:"application/json",type:"POST"}).done((function(o){$("#groupName").val(""),newGroup={group_name:o.name,group_id:o.id,members:[]},groups.push(newGroup),console.log(groups),$("#createGroupModal").modal("hide")}))})),$("#createGroupModal").modal("show")})),$("#nav-deleteGroups").click((function(){$.ajax("/groups",{data:JSON.stringify({}),contentType:"application/json",type:"DELETE"}).done((function(o){groups=o,$("#menuModal").modal("hide")}))}));
//# sourceMappingURL=admin.c8350f7c.js.map
