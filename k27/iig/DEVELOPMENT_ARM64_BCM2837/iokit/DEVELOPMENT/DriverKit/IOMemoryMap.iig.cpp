/* iig(DriverKit-427.100.5 Apr 30 2025 01:57:02) generated from IOMemoryMap.iig */

#undef	IIG_IMPLEMENTATION
#define	IIG_IMPLEMENTATION 	IOMemoryMap.iig

#if KERNEL
#include <libkern/c++/OSString.h>
#else
#include <DriverKit/DriverKit.h>
#endif /* KERNEL */
#include <DriverKit/IOReturn.h>
#include <DriverKit/IOMemoryMap.h>


#if __has_builtin(__builtin_load_member_function_pointer)
#define SimpleMemberFunctionCast(cfnty, self, func) (cfnty)__builtin_load_member_function_pointer(self, func)
#else
#define SimpleMemberFunctionCast(cfnty, self, func) OSMemberFunctionCast(cfnty, &(self), func)
#endif


struct IOMemoryMap__CopyState_Msg_Content
{
    IORPCMessage __hdr;
    OSObjectRef  __object;
};
#pragma pack(4)
struct IOMemoryMap__CopyState_Msg
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t __object__descriptor;
};
struct IOMemoryMap__CopyState_Msg_With_Content
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t __object__descriptor;
    IOMemoryMap__CopyState_Msg_Content content;
};
#pragma pack()
#define IOMemoryMap__CopyState_Msg_ObjRefs (1)

struct IOMemoryMap__CopyState_Rpl_Content
{
    IORPCMessage __hdr;
    _IOMemoryMapPrivateState  state;
};
#pragma pack(4)
struct IOMemoryMap__CopyState_Rpl
{
    IORPCMessageMach           mach;
};
struct IOMemoryMap__CopyState_Rpl_With_Content
{
    IORPCMessageMach           mach;
    IOMemoryMap__CopyState_Rpl_Content content;
};
#pragma pack()
#define IOMemoryMap__CopyState_Rpl_ObjRefs (0)


typedef union
{
    const IORPC rpc;
    struct
    {
#ifdef KERNEL
        const struct IOMemoryMap__CopyState_Msg * message;
#else /* KERNEL */
        const struct IOMemoryMap__CopyState_Msg_With_Content * message;
#endif /* KERNEL */
        struct IOMemoryMap__CopyState_Rpl_With_Content       * reply;
        uint32_t sendSize;
        uint32_t replySize;
#ifdef KERNEL
        const struct IOMemoryMap__CopyState_Msg_Content * kernelContent;
#endif /* KERNEL */
    };
} IOMemoryMap__CopyState_Invocation;
#if !KERNEL
extern OSMetaClass * gOSContainerMetaClass;
extern OSMetaClass * gOSDataMetaClass;
extern OSMetaClass * gOSNumberMetaClass;
extern OSMetaClass * gOSStringMetaClass;
extern OSMetaClass * gOSBooleanMetaClass;
extern OSMetaClass * gOSDictionaryMetaClass;
extern OSMetaClass * gOSArrayMetaClass;
extern OSMetaClass * gOSSetMetaClass;
extern OSMetaClass * gOSOrderedSetMetaClass;
extern OSMetaClass * gIODispatchQueueMetaClass;
#endif /* !KERNEL */

#if !KERNEL

#define IOMemoryMap_QueueNames  ""

#define IOMemoryMap_MethodNames  ""

#define IOMemoryMapMetaClass_MethodNames  ""

struct OSClassDescription_IOMemoryMap_t
{
    OSClassDescription base;
    uint64_t           methodOptions[2 * 0];
    uint64_t           metaMethodOptions[2 * 0];
    char               queueNames[sizeof(IOMemoryMap_QueueNames)];
    char               methodNames[sizeof(IOMemoryMap_MethodNames)];
    char               metaMethodNames[sizeof(IOMemoryMapMetaClass_MethodNames)];
};

const struct OSClassDescription_IOMemoryMap_t
OSClassDescription_IOMemoryMap =
{
    .base =
    {
        .descriptionSize         = sizeof(OSClassDescription_IOMemoryMap_t),
        .name                    = "IOMemoryMap",
        .superName               = "OSObject",
        .methodOptionsSize       = 2 * sizeof(uint64_t) * 0,
        .methodOptionsOffset     = __builtin_offsetof(struct OSClassDescription_IOMemoryMap_t, methodOptions),
        .metaMethodOptionsSize   = 2 * sizeof(uint64_t) * 0,
        .metaMethodOptionsOffset = __builtin_offsetof(struct OSClassDescription_IOMemoryMap_t, metaMethodOptions),
        .queueNamesSize       = sizeof(IOMemoryMap_QueueNames),
        .queueNamesOffset     = __builtin_offsetof(struct OSClassDescription_IOMemoryMap_t, queueNames),
        .methodNamesSize         = sizeof(IOMemoryMap_MethodNames),
        .methodNamesOffset       = __builtin_offsetof(struct OSClassDescription_IOMemoryMap_t, methodNames),
        .metaMethodNamesSize     = sizeof(IOMemoryMapMetaClass_MethodNames),
        .metaMethodNamesOffset   = __builtin_offsetof(struct OSClassDescription_IOMemoryMap_t, metaMethodNames),
        .flags                   = 1*kOSClassCanRemote,
        .resv1                   = {0},
    },
    .methodOptions =
    {
    },
    .metaMethodOptions =
    {
    },
    .queueNames      = IOMemoryMap_QueueNames,
    .methodNames     = IOMemoryMap_MethodNames,
    .metaMethodNames = IOMemoryMapMetaClass_MethodNames,
};

OSMetaClass * gIOMemoryMapMetaClass;

static kern_return_t
IOMemoryMap_New(OSMetaClass * instance);

const OSClassLoadInformation
IOMemoryMap_Class = 
{
    .description       = &OSClassDescription_IOMemoryMap.base,
    .metaPointer       = &gIOMemoryMapMetaClass,
    .version           = 1,
    .instanceSize      = sizeof(IOMemoryMap),

    .resv2             = {0},

    .New               = &IOMemoryMap_New,
    .resv3             = {0},

};

extern const void * const
gIOMemoryMap_Declaration;
const void * const
gIOMemoryMap_Declaration
__attribute__((used,visibility("hidden"),section("__DATA_CONST,__osclassinfo,regular,no_dead_strip"),no_sanitize("address")))
    = &IOMemoryMap_Class;

static kern_return_t
IOMemoryMap_New(OSMetaClass * instance)
{
    if (!new(instance) IOMemoryMapMetaClass) return (kIOReturnNoMemory);
    return (kIOReturnSuccess);
}

kern_return_t
IOMemoryMapMetaClass::New(OSObject * instance)
{
    if (!new(instance) IOMemoryMap) return (kIOReturnNoMemory);
    return (kIOReturnSuccess);
}

#endif /* !KERNEL */

#ifdef KERNEL
#define MESSAGE_CONTENT(__field) (messageContent->__field)
#else /* KERNEL */
#define MESSAGE_CONTENT(__field) (message->content.__field)
#endif /* KERNEL */

kern_return_t
IOMemoryMap::Dispatch(const IORPC rpc)
{
    return _Dispatch(this, rpc);
}

kern_return_t
IOMemoryMap::_Dispatch(IOMemoryMap * self, const IORPC rpc)
{
    kern_return_t ret = kIOReturnUnsupported;
#ifdef KERNEL
    IORPCMessage * msg = rpc.kernelContent;
#else /* KERNEL */
    IORPCMessage * msg = IORPCMessageFromMach(rpc.message, false);
#endif /* KERNEL */

    switch (msg->msgid)
    {
#if KERNEL
        case IOMemoryMap__CopyState_ID:
        {
            ret = IOMemoryMap::_CopyState_Invoke(rpc, self, SimpleMemberFunctionCast(IOMemoryMap::_CopyState_Handler, *self, &IOMemoryMap::_CopyState_Impl));
            break;
        }
#endif /* !KERNEL */

        default:
            ret = OSObject::_Dispatch(self, rpc);
            break;
    }

    return (ret);
}

#if KERNEL
kern_return_t
IOMemoryMap::MetaClass::Dispatch(const IORPC rpc)
{
#else /* KERNEL */
kern_return_t
IOMemoryMapMetaClass::Dispatch(const IORPC rpc)
{
#endif /* !KERNEL */

    kern_return_t ret = kIOReturnUnsupported;
#ifdef KERNEL
    IORPCMessage * msg = rpc.kernelContent;
#else /* KERNEL */
    IORPCMessage * msg = IORPCMessageFromMach(rpc.message, false);
#endif /* KERNEL */

    switch (msg->msgid)
    {

        default:
            ret = OSMetaClassBase::Dispatch(rpc);
            break;
    }

    return (ret);
}

kern_return_t
IOMemoryMap::_CopyState(
        _IOMemoryMapPrivateState * state,
        OSDispatchMethod supermethod)
{
    kern_return_t ret;
    union
    {
        IOMemoryMap__CopyState_Msg_With_Content msg;
        struct
        {
            IOMemoryMap__CopyState_Rpl_With_Content rpl;
            mach_msg_max_trailer_t trailer;
        } rpl;
    } buf;
    struct IOMemoryMap__CopyState_Msg_With_Content * msg = &buf.msg;
    struct IOMemoryMap__CopyState_Rpl_With_Content * rpl = &buf.rpl.rpl;

    memset(msg, 0, sizeof(*msg));
    msg->mach.msgh.msgh_id   = kIORPCVersion190615;
    msg->mach.msgh.msgh_size = sizeof(*msg);
    msg->content.__hdr.flags = 0*kIORPCMessageOneway
                             | 1*kIORPCMessageSimpleReply
                             | 0*kIORPCMessageLocalHost
                             | 0*kIORPCMessageOnqueue;
    msg->content.__hdr.msgid = IOMemoryMap__CopyState_ID;
    msg->content.__object = (OSObjectRef) this;
    msg->content.__hdr.objectRefs = IOMemoryMap__CopyState_Msg_ObjRefs;
    msg->mach.msgh_body.msgh_descriptor_count = 1;

    msg->__object__descriptor.type = MACH_MSG_PORT_DESCRIPTOR;

#ifdef KERNEL
    IORPC rpc = { .message = &buf.msg.mach, .reply = &buf.rpl.rpl.mach, .sendSize = sizeof(buf.msg), .replySize = sizeof(buf.rpl), .kernelContent = &buf.msg.content.__hdr };
#else /* KERNEL */
    IORPC rpc = { .message = &buf.msg.mach, .reply = &buf.rpl.rpl.mach, .sendSize = sizeof(buf.msg), .replySize = sizeof(buf.rpl) };
#endif /* KERNEL */
    if (supermethod) ret = supermethod((OSObject *)this, rpc);
    else             ret = ((OSObject *)this)->Invoke(rpc);

    if (kIOReturnSuccess == ret)
    do {
        {
            if (rpl->mach.msgh.msgh_size                  != sizeof(*rpl)) { ret = kIOReturnIPCError; break; };
            if (rpl->content.__hdr.msgid                  != IOMemoryMap__CopyState_ID) { ret = kIOReturnIPCError; break; };
            if (rpl->mach.msgh_body.msgh_descriptor_count != 0) { ret = kIOReturnIPCError; break; };
            if (IOMemoryMap__CopyState_Rpl_ObjRefs   != rpl->content.__hdr.objectRefs) { ret = kIOReturnIPCError; break; };
        }
    }
    while (false);
    if (kIOReturnSuccess == ret)
    {
        if (state) *state = rpl->content.state;
    }


    return (ret);
}

kern_return_t
IOMemoryMap::_CopyState_Invoke(const IORPC _rpc,
        OSMetaClassBase * target,
        _CopyState_Handler func)
{
    IOMemoryMap__CopyState_Invocation rpc = { _rpc };
    IOMemoryMap__CopyState_Rpl_With_Content * reply = rpc.reply;
#ifdef KERNEL
    const IOMemoryMap__CopyState_Msg *         message = rpc.message;
    const IOMemoryMap__CopyState_Msg_Content * messageContent = rpc.kernelContent;
#else /* KERNEL */
    const IOMemoryMap__CopyState_Msg_With_Content * message = rpc.message;
#endif /* KERNEL */
#if __has_builtin(__builtin_assume)
    __builtin_assume(reply != NULL);
#endif /* __has_builtin(__builtin_assume) */
    kern_return_t ret;

    if (1 != message->mach.msgh_body.msgh_descriptor_count) return (kIOReturnIPCError);
    if (IOMemoryMap__CopyState_Msg_ObjRefs != MESSAGE_CONTENT(__hdr.objectRefs)) return (kIOReturnIPCError);
    if (rpc.sendSize < sizeof(IOMemoryMap__CopyState_Msg_With_Content)) return (kIOReturnIPCError);
    if (reply != NULL && rpc.replySize < sizeof(*reply)) return (kIOReturnIPCError);

    ret = (*func)(target,
        &reply->content.state);

    if (kIOReturnSuccess != ret) return (ret);

    reply->content.__hdr.msgid = IOMemoryMap__CopyState_ID;
    reply->content.__hdr.flags = kIORPCMessageOneway;
    reply->mach.msgh.msgh_id   = kIORPCVersion190615Reply;
    reply->mach.msgh.msgh_size = sizeof(*reply);
    reply->mach.msgh_body.msgh_descriptor_count = 0;
    reply->content.__hdr.objectRefs = IOMemoryMap__CopyState_Rpl_ObjRefs;

    return (ret);
}



